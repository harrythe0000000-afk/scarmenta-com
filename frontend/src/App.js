import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { LayoutDashboard, ArrowDownToLine, ScrollText, LifeBuoy, Users, ShieldAlert, Settings2, Receipt } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import DashboardShell from "@/components/DashboardShell";
import Landing from "@/pages/Landing";
import { Login, Register, ForgotPassword, ResetPassword, VerifyEmail } from "@/pages/AuthPages";
import UserOverview from "@/pages/user/Overview";
import UserDeposits from "@/pages/user/Deposits";
import UserStatement from "@/pages/user/Statement";
import UserSupport from "@/pages/user/Support";
import AdminOverview from "@/pages/admin/Overview";
import AdminDeposits from "@/pages/admin/Deposits";
import AdminUsers from "@/pages/admin/Users";
import AdminTransactions from "@/pages/admin/Transactions";
import AdminFraud from "@/pages/admin/Fraud";
import AdminSupport from "@/pages/admin/Support";
import AdminSettings from "@/pages/admin/Settings";

const USER_NAV = [
  { id: "user-overview", to: "/app", end: true, label: "Overview", icon: LayoutDashboard },
  { id: "user-deposits", to: "/app/deposits", label: "Deposits", icon: ArrowDownToLine },
  { id: "user-statement", to: "/app/statement", label: "Statement", icon: ScrollText },
  { id: "user-support", to: "/app/support", label: "Support", icon: LifeBuoy },
];

const ADMIN_NAV = [
  { id: "admin-overview", to: "/admin", end: true, label: "Cockpit", icon: LayoutDashboard },
  { id: "admin-deposits", to: "/admin/deposits", label: "Deposits", icon: ArrowDownToLine },
  { id: "admin-users", to: "/admin/users", label: "Users", icon: Users },
  { id: "admin-transactions", to: "/admin/transactions", label: "Transactions", icon: Receipt },
  { id: "admin-fraud", to: "/admin/fraud", label: "Fraud Monitor", icon: ShieldAlert },
  { id: "admin-support", to: "/admin/support", label: "Support", icon: LifeBuoy },
  { id: "admin-settings", to: "/admin/settings", label: "Fee Config", icon: Settings2 },
];

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/app" element={<ProtectedRoute role="user"><DashboardShell nav={USER_NAV} area="Player Account" /></ProtectedRoute>}>
            <Route index element={<UserOverview />} />
            <Route path="deposits" element={<UserDeposits />} />
            <Route path="statement" element={<UserStatement />} />
            <Route path="support" element={<UserSupport />} />
          </Route>
          <Route path="/admin" element={<ProtectedRoute role="admin"><DashboardShell nav={ADMIN_NAV} area="Admin Cockpit" /></ProtectedRoute>}>
            <Route index element={<AdminOverview />} />
            <Route path="deposits" element={<AdminDeposits />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="transactions" element={<AdminTransactions />} />
            <Route path="fraud" element={<AdminFraud />} />
            <Route path="support" element={<AdminSupport />} />
            <Route path="settings" element={<AdminSettings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" richColors />
    </AuthProvider>
  );
}

export default App;
