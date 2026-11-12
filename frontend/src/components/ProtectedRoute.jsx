import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { homeFor, isTeam } from "@/lib/roles";

export const FullLoader = () => (
  <div className="min-h-screen grid place-items-center bg-[#05040A]" data-testid="page-loader">
    <div className="h-10 w-10 rounded-full border-2 border-purple-500/30 border-t-purple-400 animate-spin" />
  </div>
);

export default function ProtectedRoute({ role, children }) {
  const { user } = useAuth();
  if (user === null) return <FullLoader />;
  if (!user) return <Navigate to={role === "admin" || role === "owner" ? "/admin/login" : "/login"} replace />;
  if (role === "admin" && !isTeam(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  if (role === "owner" && user.role !== "admin") return <Navigate to={homeFor(user.role)} replace />;
  if ((role === "user" || role === "agent") && user.role !== role) return <Navigate to={homeFor(user.role)} replace />;
  return children;
}
