import { MotionConfig } from 'framer-motion';
import React, { Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import { AuthProvider, ProtectedRoute } from './context/AuthContext';
import { MeetingProvider } from './context/MeetingContext';
import { translate } from './hooks/useTranslation';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import Home from './pages/Home';
import MeetingRoom from './pages/MeetingRoom';

function MeetingRoomWrapper() {
  return (
    <MeetingProvider>
      <MeetingRoom />
    </MeetingProvider>
  );
}


const PageLoader: React.FC = () => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
      fontSize: '1rem',
      color: '#888',
    }}
    role="status"
    aria-live="polite"
    aria-label={translate('app.loadingPage')}
  >
    {translate('app.loading')}
  </div>
);

const App: React.FC = () => {
  return (
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <ErrorBoundary>
          <AuthProvider>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />

                {/* Protected routes — redirect to /login when not authenticated */}
                <Route
                  path="/"
                  element={
                    <ProtectedRoute>
                      <Home />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/meeting/:roomId"
                  element={
                    <ProtectedRoute>
                      <MeetingRoomWrapper />
                    </ProtectedRoute>
                  }
                />

                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </AuthProvider>
        </ErrorBoundary>
      </BrowserRouter>
    </MotionConfig>
  );
};

export default App;
