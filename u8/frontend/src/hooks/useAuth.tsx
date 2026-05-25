import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession,
} from 'amazon-cognito-identity-js';

const POOL_DATA = {
  UserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
  ClientId: import.meta.env.VITE_COGNITO_CLIENT_ID || '',
};

const userPool = new CognitoUserPool(POOL_DATA);

export interface AuthUser {
  sub: string;
  email: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  confirmSignUp: (email: string, code: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  signOut: () => void;
  getAccessToken: () => Promise<string>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    const cognitoUser = userPool.getCurrentUser();
    if (cognitoUser) {
      cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (!err && session?.isValid()) {
          const payload = session.getIdToken().decodePayload();
          setUser({ sub: payload['sub'], email: payload['email'] });
        }
        setIsLoading(false);
      });
    } else {
      setIsLoading(false);
    }
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const cognitoUser = new CognitoUser({ Username: email, Pool: userPool });
    const authDetails = new AuthenticationDetails({ Username: email, Password: password });

    return new Promise<void>((resolve, reject) => {
      cognitoUser.authenticateUser(authDetails, {
        onSuccess: (session) => {
          const payload = session.getIdToken().decodePayload();
          setUser({ sub: payload['sub'], email: payload['email'] });
          resolve();
        },
        onFailure: (err) => reject(err),
      });
    });
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    return new Promise<void>((resolve, reject) => {
      userPool.signUp(email, password, [], [], (err) => {
        if (err) {
          reject(err);
        } else {
          resolve();
        }
      });
    });
  }, []);

  const confirmSignUp = useCallback(async (email: string, code: string) => {
    const cognitoUser = new CognitoUser({ Username: email, Pool: userPool });
    return new Promise<void>((resolve, reject) => {
      cognitoUser.confirmRegistration(code, true, (err) => {
        if (err) {
          reject(err);
        } else {
          resolve();
        }
      });
    });
  }, []);

  const demoLogin = useCallback(async () => {
    await signIn('demo@example.com', 'DemoPass123!');
  }, [signIn]);

  const signOut = useCallback(() => {
    const cognitoUser = userPool.getCurrentUser();
    if (cognitoUser) {
      cognitoUser.signOut();
    }
    setUser(null);
  }, []);

  const getAccessToken = useCallback(async (): Promise<string> => {
    const cognitoUser = userPool.getCurrentUser();
    if (!cognitoUser) throw new Error('Not authenticated');

    return new Promise((resolve, reject) => {
      cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session) {
          setUser(null);
          reject(new Error('Session expired'));
          return;
        }
        if (!session.isValid()) {
          // Try refresh
          const refreshToken = session.getRefreshToken();
          cognitoUser.refreshSession(refreshToken, (refreshErr, newSession) => {
            if (refreshErr || !newSession) {
              setUser(null);
              reject(new Error('Session expired'));
              return;
            }
            resolve(newSession.getIdToken().getJwtToken());
          });
          return;
        }
        resolve(session.getIdToken().getJwtToken());
      });
    });
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, signIn, signUp, confirmSignUp, demoLogin, signOut, getAccessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
