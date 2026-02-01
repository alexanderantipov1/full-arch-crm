import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/hooks/use-auth";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const TIMEOUT_DURATION = 15 * 60 * 1000; // 15 minutes in milliseconds
const WARNING_DURATION = 60 * 1000; // Show warning 1 minute before timeout

export function SessionTimeout() {
  const { user, logout } = useAuth();
  const [showWarning, setShowWarning] = useState(false);
  const [timeLeft, setTimeLeft] = useState(60);
  const [lastActivity, setLastActivity] = useState(Date.now());

  const resetTimer = useCallback(() => {
    setLastActivity(Date.now());
    setShowWarning(false);
    setTimeLeft(60);
  }, []);

  useEffect(() => {
    if (!user) return;

    const activityEvents = ["mousedown", "keydown", "scroll", "touchstart", "click"];
    
    const handleActivity = () => {
      setLastActivity(Date.now());
      if (showWarning) {
        setShowWarning(false);
        setTimeLeft(60);
      }
    };

    activityEvents.forEach((event) => {
      window.addEventListener(event, handleActivity, { passive: true });
    });

    return () => {
      activityEvents.forEach((event) => {
        window.removeEventListener(event, handleActivity);
      });
    };
  }, [user, showWarning]);

  useEffect(() => {
    if (!user) return;

    const checkInterval = setInterval(() => {
      const now = Date.now();
      const timeSinceActivity = now - lastActivity;
      
      if (timeSinceActivity >= TIMEOUT_DURATION) {
        logout();
        setShowWarning(false);
      } else if (timeSinceActivity >= TIMEOUT_DURATION - WARNING_DURATION) {
        setShowWarning(true);
        const remaining = Math.ceil((TIMEOUT_DURATION - timeSinceActivity) / 1000);
        setTimeLeft(remaining);
      }
    }, 1000);

    return () => clearInterval(checkInterval);
  }, [user, lastActivity, logout]);

  if (!user) return null;

  return (
    <AlertDialog open={showWarning} onOpenChange={setShowWarning}>
      <AlertDialogContent data-testid="session-timeout-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>Session Timeout Warning</AlertDialogTitle>
          <AlertDialogDescription>
            Your session will expire in <span className="font-bold text-foreground">{timeLeft} seconds</span> due to inactivity.
            <br />
            <br />
            For HIPAA compliance, sessions automatically end after 15 minutes of inactivity to protect patient data.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => logout()} data-testid="button-logout-now">
            Log Out Now
          </AlertDialogCancel>
          <AlertDialogAction onClick={resetTimer} data-testid="button-continue-session">
            Continue Session
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
