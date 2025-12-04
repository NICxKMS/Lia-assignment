import React, { useState, useEffect, useCallback } from 'react'
import { authApi } from '../lib/api'
import type { User } from '../lib/api'
import { AuthContext } from './AuthContext'

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Validate stored auth on mount
  useEffect(() => {
    const validateAuth = async () => {
      const storedToken = localStorage.getItem('token')
      
      if (storedToken) {
        try {
          // Validate token by fetching user data
          const userData = await authApi.me()
          setToken(storedToken)
          setUser(userData)
          localStorage.setItem('user', JSON.stringify(userData))
        } catch {
          // Token is invalid, clear it
          localStorage.removeItem('token')
          localStorage.removeItem('user')
        }
      }
      setIsLoading(false)
    }
    
    validateAuth()
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const response = await authApi.login(email, password)
    
    localStorage.setItem('token', response.access_token)
    localStorage.setItem('user', JSON.stringify(response.user))
    
    setToken(response.access_token)
    setUser(response.user)
  }, [])

  const register = useCallback(async (email: string, username: string, password: string) => {
    const response = await authApi.register(email, username, password)
    
    localStorage.setItem('token', response.access_token)
    localStorage.setItem('user', JSON.stringify(response.user))
    
    setToken(response.access_token)
    setUser(response.user)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setToken(null)
    setUser(null)
  }, [])

  const value = {
    user,
    token,
    isLoading,
    isAuthenticated: !!token && !!user,
    login,
    register,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
