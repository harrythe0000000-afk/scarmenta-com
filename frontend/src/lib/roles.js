export const homeFor = (role) => (role === "user" ? "/app" : role === "agent" ? "/agent" : "/admin");
export const isTeam = (role) => role === "admin" || role === "staff";
