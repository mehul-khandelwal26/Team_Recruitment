"""GitHub signal analyzer using official GitHub REST API.

Extracts verifiable public GitHub metrics:
- Public repository count
- Repository metadata (stars, languages, top repositories)
- Recent activity / commit metrics (public events)
- Profile verification

Validates profile URLs and usernames, handles rate limits, inaccessible profiles,
and network failures gracefully without treating missing data as zero or using
unreliable metrics.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.config import (
    GITHUB_API_BASE_URL,
    GITHUB_REQUEST_TIMEOUT,
    GITHUB_TOKEN,
)
from app.schemas.ingestion import MemberSchema
from app.signals.base import BaseSignalExtractor
from app.signals.schemas import (
    ExtractedSignal,
    ExtractorDescriptor,
    SignalDefinition,
    SignalEvidence,
    SignalStatus,
)

# Valid GitHub username regex according to GitHub username constraints:
# 1-39 alphanumeric characters or single hyphens, not beginning or ending with hyphen.
_GITHUB_USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$")


def extract_and_validate_github_username(raw_val: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Extract and validate GitHub username from a URL or username string.

    Returns:
        (username, error_message):
        - (None, None) if raw_val is None or empty (missing input).
        - (username, None) if raw_val is a valid username or GitHub profile URL.
        - (None, error_message) if raw_val is invalid (e.g. invalid URL, invalid characters).
    """
    if raw_val is None:
        return None, None

    cleaned = str(raw_val).strip()
    if not cleaned:
        return None, None

    # Handle leading '@' if user provided '@username'
    if cleaned.startswith("@"):
        cleaned = cleaned[1:].strip()

    # If it contains URL parts
    if "://" in cleaned or cleaned.startswith("github.com") or cleaned.startswith("www.github.com"):
        candidate_url = cleaned if "://" in cleaned else f"https://{cleaned}"
        try:
            parsed = urlparse(candidate_url)
        except Exception:
            return None, f"Malformed URL: '{raw_val}'"

        netloc = (parsed.netloc or "").lower()
        if "github.com" not in netloc:
            return None, f"URL '{raw_val}' is not a GitHub URL (domain: {netloc})."

        path_segments = [seg for seg in parsed.path.strip("/").split("/") if seg]
        if not path_segments:
            return None, f"GitHub URL '{raw_val}' does not contain a profile username."

        username = path_segments[0]
    else:
        # Raw username string
        username = cleaned

    # Strip any trailing characters that might accidentally be present
    username = username.strip("/")

    if not _GITHUB_USERNAME_REGEX.match(username):
        return None, f"'{username}' is not a valid GitHub username."

    return username, None


class GitHubAnalyzer(BaseSignalExtractor):
    """Analyzer for public GitHub developer profiles and activity."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._token = token or GITHUB_TOKEN
        self._base_url = (base_url or GITHUB_API_BASE_URL).rstrip("/")
        self._timeout = timeout or GITHUB_REQUEST_TIMEOUT
        self._custom_client = http_client
        # In-memory per-run cache to avoid duplicate API calls for identical usernames
        self._user_cache: dict[str, dict[str, Any]] = {}
        self._repos_cache: dict[str, list[dict[str, Any]]] = {}
        self._events_cache: dict[str, list[dict[str, Any]]] = {}

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            extractor_id="github_analyzer",
            name="GitHub Activity & Repo Analyzer",
            description="Analyzes public repositories, commit recency, primary languages, and contributions.",
            category="technical",
            required_inputs=["github_url"],
            optional_inputs=["name"],
            produced_signals=[
                "github_public_repo_count",
                "github_repo_metadata",
                "github_recent_activity",
                "github_profile_verified",
            ],
            signals=[
                SignalDefinition(
                    signal_key="github_public_repo_count",
                    name="Public Repository Count",
                    description="Total count of public repositories on the candidate's GitHub profile.",
                    category="technical",
                    value_type="integer",
                    unit="repositories",
                ),
                SignalDefinition(
                    signal_key="github_repo_metadata",
                    name="Repository Metadata",
                    description="Public repository details including total stars, primary languages, and top repos.",
                    category="technical",
                    value_type="dict",
                ),
                SignalDefinition(
                    signal_key="github_recent_activity",
                    name="Recent GitHub Activity",
                    description="Recent public activity, push events, and commit recency metrics.",
                    category="technical",
                    value_type="dict",
                ),
                SignalDefinition(
                    signal_key="github_profile_verified",
                    name="GitHub Profile Verified",
                    description="Verifies that the GitHub profile exists and is publicly accessible.",
                    category="technical",
                    value_type="boolean",
                ),
            ],
            is_enabled_by_default=False,
            optional_config={
                "github_token": "Optional GitHub PAT for higher rate limits",
                "include_forks": "Whether to include forked repositories in metadata (default: False)",
                "max_repos_inspected": "Maximum repositories to inspect for metadata (default: 30)",
            },
        )

    def _get_client(self) -> httpx.Client:
        if self._custom_client is not None:
            return self._custom_client
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Team-Recruitment-Tool/0.1",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return httpx.Client(
            headers=headers,
            timeout=httpx.Timeout(self._timeout, connect=5.0),
            follow_redirects=True,
        )

    def extract(
        self,
        member: MemberSchema,
        selected_signals: Optional[set[str]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> list[ExtractedSignal]:
        """Extract requested GitHub signals for a team member."""
        target_signals = selected_signals or set(self.descriptor.produced_signals)
        results: list[ExtractedSignal] = []

        # Find raw input: check canonical github_url, then custom_fields
        raw_input = member.github_url
        if raw_input is None:
            raw_input = member.custom_fields.get("github_url") or member.custom_fields.get("github")

        # 1. Check for missing input -> NOT_APPLICABLE
        username, parse_error = extract_and_validate_github_username(raw_input)
        if raw_input is None or (isinstance(raw_input, str) and not raw_input.strip()):
            for sig in target_signals:
                results.append(
                    ExtractedSignal(
                        signal_key=sig,
                        category="technical",
                        value=None,
                        status=SignalStatus.NOT_APPLICABLE,
                        error_message="No GitHub profile URL or username provided.",
                        evidence=SignalEvidence(
                            source="github",
                            raw_input=None,
                            metadata={"reason": "missing_input"},
                        ),
                    )
                )
            return results

        # 2. Check for invalid input -> FAILED
        if parse_error or not username:
            for sig in target_signals:
                results.append(
                    ExtractedSignal(
                        signal_key=sig,
                        category="technical",
                        value=None,
                        status=SignalStatus.FAILED,
                        error_message=parse_error or "Invalid GitHub username or URL format.",
                        evidence=SignalEvidence(
                            source="github",
                            raw_input=str(raw_input),
                            metadata={"reason": "invalid_input_format"},
                        ),
                    )
                )
            return results

        # 3. Query GitHub API with sensible timeouts and error handling
        client_to_close: Optional[httpx.Client] = None
        client = self._custom_client
        if client is None:
            client = self._get_client()
            client_to_close = client

        try:
            # Fetch user profile if needed
            user_data, user_err_status, user_err_msg = self._fetch_user(client, username, raw_input)
            if user_err_status is not None:
                # User fetch failed (e.g. 404, rate limit, timeout)
                for sig in target_signals:
                    results.append(
                        ExtractedSignal(
                            signal_key=sig,
                            category="technical",
                            value=None,
                            status=user_err_status,
                            error_message=user_err_msg,
                            evidence=SignalEvidence(
                                source="github_api",
                                raw_input=str(raw_input),
                                metadata={"username": username, "error": user_err_msg},
                            ),
                        )
                    )
                return results

            # We have valid user profile
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Signal: github_profile_verified
            if "github_profile_verified" in target_signals:
                results.append(
                    ExtractedSignal(
                        signal_key="github_profile_verified",
                        category="technical",
                        value=True,
                        status=SignalStatus.EXTRACTED,
                        evidence=SignalEvidence(
                            source="github_api",
                            raw_input=str(raw_input),
                            extracted_at=timestamp,
                            confidence=1.0,
                            metadata={
                                "username": username,
                                "html_url": user_data.get("html_url"),
                                "name": user_data.get("name"),
                                "bio": user_data.get("bio"),
                                "created_at": user_data.get("created_at"),
                            },
                        ),
                    )
                )

            # Signal: github_public_repo_count
            if "github_public_repo_count" in target_signals:
                public_repos = int(user_data.get("public_repos", 0))
                results.append(
                    ExtractedSignal(
                        signal_key="github_public_repo_count",
                        category="technical",
                        value=public_repos,
                        status=SignalStatus.EXTRACTED,
                        evidence=SignalEvidence(
                            source="github_api",
                            raw_input=str(raw_input),
                            extracted_at=timestamp,
                            confidence=1.0,
                            metadata={
                                "username": username,
                                "public_repos": public_repos,
                                "profile_url": user_data.get("html_url"),
                            },
                        ),
                    )
                )

            # Signal: github_repo_metadata
            if "github_repo_metadata" in target_signals:
                repos_data, repos_err = self._fetch_repos(client, username)
                if repos_err:
                    results.append(
                        ExtractedSignal(
                            signal_key="github_repo_metadata",
                            category="technical",
                            value=None,
                            status=SignalStatus.FAILED,
                            error_message=f"Failed to fetch repositories: {repos_err}",
                            evidence=SignalEvidence(
                                source="github_api",
                                raw_input=str(raw_input),
                                metadata={"username": username, "error": repos_err},
                            ),
                        )
                    )
                else:
                    repo_summary = self._compute_repo_metadata(repos_data, user_data)
                    results.append(
                        ExtractedSignal(
                            signal_key="github_repo_metadata",
                            category="technical",
                            value=repo_summary,
                            status=SignalStatus.EXTRACTED,
                            evidence=SignalEvidence(
                                source="github_api",
                                raw_input=str(raw_input),
                                extracted_at=timestamp,
                                confidence=1.0,
                                metadata={
                                    "username": username,
                                    "repos_inspected": len(repos_data),
                                    "total_stars": repo_summary["total_stars"],
                                    "languages_count": len(repo_summary["primary_languages"]),
                                },
                            ),
                        )
                    )

            # Signal: github_recent_activity
            if "github_recent_activity" in target_signals:
                events_data, events_err = self._fetch_events(client, username)
                if events_err:
                    results.append(
                        ExtractedSignal(
                            signal_key="github_recent_activity",
                            category="technical",
                            value=None,
                            status=SignalStatus.FAILED,
                            error_message=f"Failed to fetch public events: {events_err}",
                            evidence=SignalEvidence(
                                source="github_api",
                                raw_input=str(raw_input),
                                metadata={"username": username, "error": events_err},
                            ),
                        )
                    )
                else:
                    activity_summary = self._compute_recent_activity(events_data)
                    results.append(
                        ExtractedSignal(
                            signal_key="github_recent_activity",
                            category="technical",
                            value=activity_summary,
                            status=SignalStatus.EXTRACTED,
                            evidence=SignalEvidence(
                                source="github_api",
                                raw_input=str(raw_input),
                                extracted_at=timestamp,
                                confidence=1.0,
                                metadata={
                                    "username": username,
                                    "events_inspected": len(events_data),
                                    "has_recent_activity": activity_summary["has_recent_activity"],
                                },
                            ),
                        )
                    )

        finally:
            if client_to_close is not None:
                client_to_close.close()

        return results

    def _fetch_user(
        self,
        client: httpx.Client,
        username: str,
        raw_input: Any,
    ) -> tuple[Optional[dict[str, Any]], Optional[SignalStatus], Optional[str]]:
        """Fetch user profile from GitHub API."""
        if username in self._user_cache:
            return self._user_cache[username], None, None

        url = f"{self._base_url}/users/{username}"
        try:
            resp = client.get(url)
        except httpx.TimeoutException:
            return None, SignalStatus.FAILED, f"Connection timed out while contacting GitHub API for user '{username}'."
        except httpx.RequestError as exc:
            return None, SignalStatus.FAILED, f"Network error contacting GitHub API: {exc}"

        if resp.status_code == 200:
            data = resp.json()
            self._user_cache[username] = data
            return data, None, None
        elif resp.status_code == 404:
            return None, SignalStatus.FAILED, f"GitHub profile '{username}' not found (HTTP 404)."
        elif resp.status_code in (403, 429):
            remaining = resp.headers.get("x-ratelimit-remaining", "")
            if remaining == "0" or "rate limit" in resp.text.lower():
                return None, SignalStatus.FAILED, "GitHub API rate limit exceeded."
            return None, SignalStatus.FAILED, f"GitHub API access forbidden (HTTP {resp.status_code})."
        else:
            return None, SignalStatus.FAILED, f"GitHub API returned unexpected status HTTP {resp.status_code}."

    def _fetch_repos(
        self,
        client: httpx.Client,
        username: str,
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        """Fetch public repos for a user."""
        if username in self._repos_cache:
            return self._repos_cache[username], None

        url = f"{self._base_url}/users/{username}/repos"
        params = {"per_page": 30, "sort": "updated", "type": "public"}
        try:
            resp = client.get(url, params=params)
        except Exception as exc:
            return [], str(exc)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                self._repos_cache[username] = data
                return data, None
            return [], "Unexpected response format for repositories."
        return [], f"HTTP {resp.status_code}"

    def _fetch_events(
        self,
        client: httpx.Client,
        username: str,
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        """Fetch public events for a user."""
        if username in self._events_cache:
            return self._events_cache[username], None

        url = f"{self._base_url}/users/{username}/events/public"
        params = {"per_page": 30}
        try:
            resp = client.get(url, params=params)
        except Exception as exc:
            return [], str(exc)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                self._events_cache[username] = data
                return data, None
            return [], "Unexpected response format for public events."
        return [], f"HTTP {resp.status_code}"

    def _compute_repo_metadata(
        self,
        repos: list[dict[str, Any]],
        user_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Summarize repository metadata from public repositories."""
        total_stars = 0
        total_forks = 0
        lang_counts: dict[str, int] = {}
        top_repos: list[dict[str, Any]] = []

        for r in repos:
            stars = int(r.get("stargazers_count", 0))
            forks = int(r.get("forks_count", 0))
            lang = r.get("language")

            total_stars += stars
            total_forks += forks
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

            top_repos.append(
                {
                    "name": r.get("name"),
                    "stars": stars,
                    "forks": forks,
                    "language": lang,
                    "html_url": r.get("html_url"),
                    "updated_at": r.get("updated_at"),
                    "is_fork": bool(r.get("fork", False)),
                }
            )

        # Sort top repos by stars descending
        top_repos.sort(key=lambda x: x["stars"], reverse=True)
        top_languages = sorted(lang_counts.keys(), key=lambda l: lang_counts[l], reverse=True)

        return {
            "total_public_repos": int(user_data.get("public_repos", len(repos))),
            "total_stars": total_stars,
            "total_forks": total_forks,
            "primary_languages": top_languages[:5],
            "language_counts": lang_counts,
            "top_repositories": top_repos[:5],
        }

    def _compute_recent_activity(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute reliable recent activity metrics from GitHub public events."""
        recent_events_count = len(events)
        push_events_count = 0
        recent_commit_count = 0
        last_active_date: Optional[str] = None

        for event in events:
            event_type = event.get("type")
            created_at = event.get("created_at")

            if last_active_date is None and created_at:
                last_active_date = created_at

            if event_type == "PushEvent":
                push_events_count += 1
                payload = event.get("payload") or {}
                commits = payload.get("commits") or []
                recent_commit_count += len(commits)

        has_recent = recent_events_count > 0
        active_90_days = False
        if last_active_date:
            try:
                # Handle ISO timestamps like 2026-10-01T12:00:00Z
                cleaned_date = last_active_date.replace("Z", "+00:00")
                event_dt = datetime.datetime.fromisoformat(cleaned_date)
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                if (now_dt - event_dt).days <= 90:
                    active_90_days = True
            except Exception:
                active_90_days = has_recent

        return {
            "recent_events_count": recent_events_count,
            "push_events_count": push_events_count,
            "recent_commit_count": recent_commit_count,
            "has_recent_activity": has_recent,
            "last_active_date": last_active_date,
            "active_in_past_90_days": active_90_days,
        }
