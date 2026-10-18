import React from 'react';
import { Link } from 'react-router-dom';
import { FileQuestion, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center p-6">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-muted-foreground mb-4">
        <FileQuestion className="h-6 w-6" />
      </div>
      <h2 className="text-xl font-bold tracking-tight text-foreground mb-1">
        Page Not Found
      </h2>
      <p className="text-sm text-muted-foreground max-w-sm mb-6">
        The requested URL was not found in the Team Recruitment Automation Tool application.
      </p>
      <Button asChild variant="default" className="gap-2">
        <Link to="/">
          <ArrowLeft className="h-4 w-4" />
          Return to Dashboard
        </Link>
      </Button>
    </div>
  );
};
