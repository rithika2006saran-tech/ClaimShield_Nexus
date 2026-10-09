import { useState, useEffect } from "react";
import { UserCircle } from "lucide-react";

export function RoleToggle() {
  const [role, setRole] = useState(() => localStorage.getItem("user-role") || "LEAD");

  useEffect(() => {
    localStorage.setItem("user-role", role);
    // When role changes, force a reload to apply permissions properly
    const prev = localStorage.getItem("prev-role");
    if (prev && prev !== role) {
      window.location.reload();
    }
    localStorage.setItem("prev-role", role);
  }, [role]);

  return (
    <div className="flex items-center gap-2 mr-4 border border-border rounded-md px-2 py-1 bg-card/50">
      <UserCircle className="h-4 w-4 text-muted-foreground" />
      <select
        value={role}
        onChange={(e) => setRole(e.target.value)}
        className="bg-transparent text-xs outline-none border-none text-muted-foreground hover:text-foreground cursor-pointer"
      >
        <option value="LEAD">SIU Lead</option>
        <option value="ANALYST">Analyst</option>
        <option value="REVIEWER">Reviewer</option>
      </select>
    </div>
  );
}
