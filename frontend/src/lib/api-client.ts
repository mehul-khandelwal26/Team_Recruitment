/**
 * Reusable HTTP API client for communication with the FastAPI backend.
 * Uses VITE_API_BASE_URL with fallback to http://localhost:8000.
 */

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : typeof window !== 'undefined'
      ? ''
      : 'http://localhost:8000'
).replace(/\/+$/, '');

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, ...rest } = options;

  let url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val));
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  const defaultHeaders: Record<string, string> = {};
  if (rest.body !== undefined && !(rest.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...rest,
      headers: {
        ...defaultHeaders,
        ...headers,
      },
    });
  } catch (err) {
    throw new ApiError(
      0,
      `Unable to connect to the backend server at ${API_BASE_URL || 'http://localhost:8000'}. Ensure the FastAPI server is running.`
    );
  }

  let data: unknown;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;
    if (data && typeof data === 'object') {
      const errObj = data as Record<string, unknown>;
      if (typeof errObj.detail === 'string') {
        errorMessage = errObj.detail;
      } else if (Array.isArray(errObj.detail)) {
        // Validation error array from FastAPI
        errorMessage = errObj.detail
          .map((item: { msg?: string; loc?: string[] }) => item.msg || JSON.stringify(item))
          .join(', ');
      }
    }
    throw new ApiError(response.status, errorMessage, data);
  }

  return data as T;
}

export const apiClient = {
  get<T>(endpoint: string, params?: RequestOptions['params'], options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'GET', params });
  },

  post<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> {
    const isFormData = body instanceof FormData;
    return request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: isFormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  put<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'DELETE' });
  },

  async upload<T>(endpoint: string, file: File, extraFields?: Record<string, string>): Promise<T> {
    const formData = new FormData();
    formData.append('file', file);
    if (extraFields) {
      for (const [key, value] of Object.entries(extraFields)) {
        formData.append(key, value);
      }
    }
    return request<T>(endpoint, {
      method: 'POST',
      body: formData,
    });
  },

  downloadBlob(endpoint: string, params?: RequestOptions['params']): Promise<{ blob: Blob; filename?: string }> {
    let url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    if (params) {
      const searchParams = new URLSearchParams();
      for (const [key, val] of Object.entries(params)) {
        if (val !== undefined && val !== null) searchParams.append(key, String(val));
      }
      const qs = searchParams.toString();
      if (qs) url += (url.includes('?') ? '&' : '?') + qs;
    }

    return fetch(url).then(async (res) => {
      if (!res.ok) throw new ApiError(res.status, `Download failed: ${res.statusText}`);
      const disposition = res.headers.get('content-disposition');
      let filename: string | undefined;
      if (disposition && disposition.includes('filename=')) {
        const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (match?.[1]) {
          filename = match[1].replace(/['"]/g, '');
        }
      }
      const blob = await res.blob();
      return { blob, filename };
    });
  },
};
