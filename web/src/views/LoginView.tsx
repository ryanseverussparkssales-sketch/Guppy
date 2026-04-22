import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, Mail, Eye, EyeOff } from 'lucide-react'
import api from '../api/client'
import './LoginView.css'

export default function LoginView() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [isSignUp, setIsSignUp] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      if (isSignUp) {
        // Sign up
        await api.post('/auth/signup', { email, password })
        setError('')
        setEmail('')
        setPassword('')
        setIsSignUp(false)
      } else {
        // Login with Turnstile token
        const response = await api.post('/auth/verify', { token: email })
        localStorage.setItem('accessToken', response.data.access_token)
        localStorage.setItem('expiresIn', response.data.expires_in)
        navigate('/')
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Authentication failed')
    } finally {
      setIsLoading(false)
    }
  }

  const handleGuestAccess = async () => {
    setIsLoading(true)
    try {
      // Get dev token for testing
      const response = await api.post('/auth/verify', { token: 'dev-token' })
      localStorage.setItem('accessToken', response.data.access_token)
      navigate('/')
    } catch (err) {
      setError('Guest access failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>Guppy</h1>
          <p>AI Assistant Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <h2>{isSignUp ? 'Create Account' : 'Login'}</h2>

          {error && <div className="login-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="email">
              <Mail size={16} />
              Email or Token
            </label>
            <input
              id="email"
              type={isSignUp ? 'email' : 'text'}
              placeholder={isSignUp ? 'your@email.com' : 'Enter token or dev-token'}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
              required
            />
          </div>

          {isSignUp && (
            <div className="form-group">
              <label htmlFor="password">
                <Lock size={16} />
                Password
              </label>
              <div className="password-input">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={isLoading}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : isSignUp ? 'Create Account' : 'Login'}
          </button>

          <div className="login-divider">or</div>

          <button
            type="button"
            className="btn btn-secondary btn-block"
            onClick={handleGuestAccess}
            disabled={isLoading}
          >
            Continue as Guest
          </button>
        </form>

        <div className="login-footer">
          {!isSignUp ? (
            <>
              <p>Don't have an account?</p>
              <button
                className="link-btn"
                onClick={() => setIsSignUp(true)}
                disabled={isLoading}
              >
                Sign up
              </button>
            </>
          ) : (
            <>
              <p>Already have an account?</p>
              <button
                className="link-btn"
                onClick={() => setIsSignUp(false)}
                disabled={isLoading}
              >
                Login
              </button>
            </>
          )}
        </div>

        <div className="login-info">
          <p>For development: Use token <code>dev-token</code></p>
        </div>
      </div>
    </div>
  )
}
