import { createContext, useCallback, useEffect, useState } from "react";
import * as authApi from "../services/authApi";
import { getRefreshToken } from "../services/tokenStore";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    if (!getRefreshToken()) {
      setLoading(false);
      return;
    }
    try {
      // Access token is memory-only, so on a hard refresh we have none yet —
      // this call will 401, the axios interceptor will use the refresh
      // token to get a new access token, then retry automatically.
      const currentUser = await authApi.fetchCurrentUser();
      setUser(currentUser);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = async (credentials) => {
    const loggedInUser = await authApi.login(credentials);
    setUser(loggedInUser);
    return loggedInUser;
  };

  const register = async (payload) => {
    const registeredUser = await authApi.register(payload);
    setUser(registeredUser);
    return registeredUser;
  };

  const logout = async () => {
    await authApi.logout(getRefreshToken());
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
