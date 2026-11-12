import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { LayoutDashboard, ArrowDownToLine, ScrollText, LifeBuoy, Users, ShieldAlert, Settings2, Receipt, Gamepad2, Gift, Plug, Dices, Award, Workflow, UserCog, ShieldCheck, Handshake, ArrowLeftRight } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Terms from "@/pages/Terms";
import Privacy from "@/pages/Privacy";
import DashboardShell from "@/components/DashboardShell";
import Landing from "@/pages/Landing";
import { Login, Register, ForgotPassword, ResetPassword, VerifyEmail, AdminLogin } from "@/pages/AuthPages";
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
import UserGames from "@/pages/user/Games";
import UserRefer from "@/pages/user/Refer";
import AdminProviders from "@/pages/admin/Providers";
import AdminGameActivity from "@/pages/admin/GameActivity";
import AdminReferrals from "@/pages/admin/Referrals";
import UserRewards from "@/pages/user/Rewards";
import AdminLossRewards from "@/pages/admin/LossRewards";
import AdminMoneyFlow from "@/pages/admin/MoneyFlow";
import AccountSettings from "@/pages/AccountSettings";
import AdminStaff from "@/pages/admin/Staff";
import AdminAgents from "@/pages/admin/Agents";
import UserTransfer from "@/pages/user/Transfer";
import AgentDashboard from "@/pages/agent/Dashboard";

const USER_NAV = [
  { id: "user-overview", to: "/app", end: true, label: "Overview", icon: LayoutDashboard },
  { id: "user-deposits", to: "/app/deposits", label: "Deposits", icon: ArrowDownToLine },
  { id: "user-transfer", to: "/app/transfer", label: "Transfer", icon: ArrowLeftRight },
  { id: "user-games", to: "/app/games", label: "Games", icon: Gamepad2 },
  { id: "user-refer", to: "/app/refer", label: "Refer & Earn", icon: Gift },
  { id: "user-rewards", to: "/app/rewards", label: "Loss Rewards", icon: Award },
  { id: "user-statement", to: "/app/statement", label: "Statement", icon: ScrollText },
  { id: "user-support", to: "/app/support", label: "Support", icon: LifeBuoy },
  { id: "user-account", to: "/app/account", label: "My Account", icon: UserCog },
];

const AGENT_NAV = [
  { id: "agent-dashboard", to: "/agent", end: true, label: "Dashboard", icon: Handshake },
  { id: "agent-account", to: "/agent/account", label: "My Account", icon: UserCog },
];

const ADMIN_NAV = [
  { id: "admin-overview", to: "/admin", end: true, label: "Cockpit", icon: LayoutDashboard },
  { id: "admin-money-flow", to: "/admin/money-flow", label: "Money Flow", icon: Workflow },
  { id: "admin-deposits", to: "/admin/deposits", label: "Deposits", icon: ArrowDownToLine },
  { id: "admin-users", to: "/admin/users", label: "Users", icon: Users },
  { id: "admin-transactions", to: "/admin/transactions", label: "Transactions", icon: Receipt },
  { id: "admin-providers", to: "/admin/providers", label: "Game Providers", icon: Plug, adminOnly: true },
  { id: "admin-game-activity", to: "/admin/game-activity", label: "Game Activity", icon: Dices },
  { id: "admin-referrals", to: "/admin/referrals", label: "Referrals", icon: Gift },
  { id: "admin-loss-rewards", to: "/admin/loss-rewards", label: "Loss Rewards", icon: Award, adminOnly: true },
  { id: "admin-fraud", to: "/admin/fraud", label: "Fraud Monitor", icon: ShieldAlert },
  { id: "admin-support", to: "/admin/support", label: "Support", icon: LifeBuoy },
  { id: "admin-agents", to: "/admin/agents", label: "Agents", icon: Handshake },
  { id: "admin-staff", to: "/admin/staff", label: "Staff", icon: ShieldCheck, adminOnly: true },
  { id: "admin-account", to: "/admin/account", label: "My Account", icon: UserCog },
  { id: "admin-settings", to: "/admin/settings", label: "Credit Config", icon: Settings2, adminOnly: true },
];

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/register" element={<Register />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/app" element={<ProtectedRoute role="user"><DashboardShell nav={USER_NAV} area="Player Account" /></ProtectedRoute>}>
            <Route index element={<UserOverview />} />
            <Route path="deposits" element={<UserDeposits />} />
            <Route path="transfer" element={<UserTransfer />} />
            <Route path="games" element={<UserGames />} />
            <Route path="refer" element={<UserRefer />} />
            <Route path="rewards" element={<UserRewards />} />
            <Route path="statement" element={<UserStatement />} />
            <Route path="support" element={<UserSupport />} />
            <Route path="account" element={<AccountSettings />} />
          </Route>
          <Route path="/admin" element={<ProtectedRoute role="admin"><DashboardShell nav={ADMIN_NAV} area="Admin Cockpit" /></ProtectedRoute>}>
            <Route index element={<AdminOverview />} />
            <Route path="deposits" element={<AdminDeposits />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="transactions" element={<AdminTransactions />} />
            <Route path="providers" element={<ProtectedRoute role="owner"><AdminProviders /></ProtectedRoute>} />
            <Route path="game-activity" element={<AdminGameActivity />} />
            <Route path="referrals" element={<AdminReferrals />} />
            <Route path="loss-rewards" element={<ProtectedRoute role="owner"><AdminLossRewards /></ProtectedRoute>} />
            <Route path="money-flow" element={<AdminMoneyFlow />} />
            <Route path="account" element={<AccountSettings />} />
            <Route path="fraud" element={<AdminFraud />} />
            <Route path="support" element={<AdminSupport />} />
            <Route path="settings" element={<ProtectedRoute role="owner"><AdminSettings /></ProtectedRoute>} />
            <Route path="staff" element={<ProtectedRoute role="owner"><AdminStaff /></ProtectedRoute>} />
            <Route path="agents" element={<AdminAgents />} />
          </Route>
          <Route path="/agent" element={<ProtectedRoute role="agent"><DashboardShell nav={AGENT_NAV} area="Agent Portal" /></ProtectedRoute>}>
            <Route index element={<AgentDashboard />} />
            <Route path="account" element={<AccountSettings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-right" richColors />
    </AuthProvider>
  );
}

export default App;
