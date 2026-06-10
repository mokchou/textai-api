import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import {
  Bot,
  FlaskConical,
  GitCompareArrows,
  LayoutDashboard,
  Radio,
  Settings2,
  SlidersHorizontal,
} from "lucide-react";
import Dashboard from "./pages/Dashboard";
import ConfigurationPage from "./pages/ConfigurationPage";
import BacktestPage from "./pages/BacktestPage";
import ComparisonPage from "./pages/ComparisonPage";
import OptimizationPage from "./pages/OptimizationPage";
import PaperPage from "./pages/PaperPage";
import AdaptivePage from "./pages/AdaptivePage";

const NAV = [
  { to: "/", label: "Tableau de bord", icon: LayoutDashboard, end: true },
  { to: "/configuration", label: "Configuration", icon: Settings2 },
  { to: "/backtest", label: "Backtest", icon: FlaskConical },
  { to: "/comparaison", label: "Comparaison", icon: GitCompareArrows },
  { to: "/optimisation", label: "Optimisation", icon: SlidersHorizontal },
  { to: "/paper", label: "Paper trading", icon: Radio },
  { to: "/adaptation", label: "Adaptation", icon: Bot },
];

export default function App() {
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-slate-800 bg-slate-900">
        <div className="flex items-center gap-2 px-4 py-5">
          <Bot className="text-sky-400" size={22} aria-hidden="true" />
          <span className="text-base font-bold tracking-tight text-slate-100">Breakout Bot</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-2" aria-label="Navigation principale">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-sky-500/15 text-sky-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                }`
              }
            >
              <Icon size={17} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
        <p className="px-4 py-3 text-[10px] text-slate-600">
          Bot de trading crypto — cassures de range
        </p>
      </aside>
      <main className="min-w-0 flex-1 p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/configuration" element={<ConfigurationPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/comparaison" element={<ComparisonPage />} />
          <Route path="/optimisation" element={<OptimizationPage />} />
          <Route path="/paper" element={<PaperPage />} />
          <Route path="/adaptation" element={<AdaptivePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
