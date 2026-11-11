import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export const FullLoader = () => (
  <div className="min-h-screen grid place-items-center bg-[#05040A]" data-testid="page-loader">
    <div className="h-10 w-10 rounded-full border-2 border-purple-500/30 border-t-purple-400 animate-spin" />
  </div>
);

export default function ProtectedRoute({ role, children }) {
  const { user } = useAuth();
  if (user === null) return <FullLoader />;
  if (!user) return <Navigate to="/login" replace />;
  if (role === "admin" && user.role !== "admin") return <Navigate to="/app" replace />;
  if (role === "user" && user.role === "admin") return <Navigate to="/admin" replace />;
  return children;
}
