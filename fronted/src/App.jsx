import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'

import WebsiteLayout from './layouts/WebsiteLayout.jsx'
import PortalLayout from './layouts/PortalLayout.jsx'
import ProtectedRoute from './components/common/ProtectedRoute.jsx'
import Loader from './components/common/Loader.jsx'

// ---------------------------------------------------------------------------
// Public website pages (lazy-loaded so the admin portal bundle stays separate)
// ---------------------------------------------------------------------------
const Home = lazy(() => import('./pages/website/Home.jsx'))
const Games = lazy(() => import('./pages/website/Games.jsx'))
const Pricing = lazy(() => import('./pages/website/Pricing.jsx'))
const BookConsole = lazy(() => import('./pages/website/BookConsole.jsx'))
const Tournaments = lazy(() => import('./pages/website/Tournaments.jsx'))
const Leaderboard = lazy(() => import('./pages/website/Leaderboard.jsx'))
const About = lazy(() => import('./pages/website/About.jsx'))
const Contact = lazy(() => import('./pages/website/Contact.jsx'))
const Login = lazy(() => import('./pages/website/Login.jsx'))
const Register = lazy(() => import('./pages/website/Register.jsx'))

// ---------------------------------------------------------------------------
// Admin portal pages
// ---------------------------------------------------------------------------
const Dashboard = lazy(() => import('./pages/portal/Dashboard.jsx'))
const WalkIns = lazy(() => import('./pages/portal/WalkIns.jsx'))
const Customers = lazy(() => import('./pages/portal/Customers.jsx'))
const Consoles = lazy(() => import('./pages/portal/Consoles.jsx'))
const PortalGames = lazy(() => import('./pages/portal/Games.jsx'))
const GamingSessions = lazy(() => import('./pages/portal/GamingSessions.jsx'))
const Inventory = lazy(() => import('./pages/portal/Inventory.jsx'))
const Sales = lazy(() => import('./pages/portal/Sales.jsx'))
const Payments = lazy(() => import('./pages/portal/Payments.jsx'))
const Expenses = lazy(() => import('./pages/portal/Expenses.jsx'))
const Reports = lazy(() => import('./pages/portal/Reports.jsx'))
const Users = lazy(() => import('./pages/portal/Users.jsx'))
const Settings = lazy(() => import('./pages/portal/Settings.jsx'))
const AuditLogs = lazy(() => import('./pages/portal/AuditLogs.jsx'))
const Notifications = lazy(() => import('./pages/portal/Notifications.jsx'))
const Betting = lazy(() => import('./pages/portal/Betting.jsx'))
const Profile = lazy(() => import('./pages/portal/Profile.jsx'))
const NotFound = lazy(() => import('./pages/portal/NotFound.jsx'))

function PageFallback() {
  return (
    <div className="ll-page-fallback">
      <Loader label="Loading page..." />
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        {/* --------------------------------------------------------------- */}
        {/* Public marketing website                                       */}
        {/* --------------------------------------------------------------- */}
        <Route element={<WebsiteLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/games" element={<Games />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/book" element={<BookConsole />} />
          <Route path="/tournaments" element={<Tournaments />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Route>

        {/* --------------------------------------------------------------- */}
        {/* Admin portal (protected)                                       */}
        {/* --------------------------------------------------------------- */}
        <Route
          path="/portal"
          element={
            <ProtectedRoute>
              <PortalLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="walk-ins" element={<WalkIns />} />
          <Route path="customers" element={<Customers />} />
          <Route path="consoles" element={<Consoles />} />
          <Route path="games" element={<PortalGames />} />
          <Route path="gaming-sessions" element={<GamingSessions />} />
          <Route path="inventory" element={<Inventory />} />
          <Route path="sales" element={<Sales />} />
          <Route path="payments" element={<Payments />} />
          <Route path="expenses" element={<Expenses />} />
          <Route path="reports" element={<Reports />} />
          <Route path="users" element={<Users />} />
          <Route path="settings" element={<Settings />} />
          <Route path="audit-logs" element={<AuditLogs />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="betting" element={<Betting />} />
          <Route path="profile" element={<Profile />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}