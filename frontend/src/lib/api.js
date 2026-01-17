/**
 * API utilities with trace_id error handling and centralized axios client.
 *
 * Usage:
 *   import { apiClient, showApiError } from '../lib/api';
 *
 *   // Make requests
 *   const response = await apiClient.get('/api/users');
 *
 *   // Handle errors
 *   catch (error) {
 *     showApiError(error, 'Failed to save user');
 *   }
 *
 * This extracts trace_id from backend error responses and displays it
 * so users can reference it when reporting issues.
 */

import axios from 'axios';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Token storage keys
const ACCESS_TOKEN_KEY = 'token';
const REFRESH_TOKEN_KEY = 'refresh_token';

// Flag to prevent multiple refresh attempts
let isRefreshing = false;
let failedQueue = [];

/**
 * Process queued requests after token refresh.
 */
const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

/**
 * Create configured axios instance with interceptors.
 */
const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor - adds auth token to requests.
 */
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Response interceptor - handles errors and token refresh.
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 Unauthorized - attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't retry auth endpoints
      if (originalRequest.url?.includes('/api/auth/')) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Wait for the refresh to complete
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

      if (!refreshToken) {
        // No refresh token - force logout
        handleAuthFailure();
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(`${API_URL}/api/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token } = response.data;
        localStorage.setItem(ACCESS_TOKEN_KEY, access_token);

        // Update default header
        apiClient.defaults.headers.common.Authorization = `Bearer ${access_token}`;

        processQueue(null, access_token);

        // Retry original request
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        handleAuthFailure();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Handle 429 Rate Limit
    if (error.response?.status === 429) {
      const retryAfter = error.response.data?.retry_after_seconds || 
                         error.response.headers?.['retry-after'] || 
                         60;
      toast.error(`Too many requests. Please wait ${retryAfter} seconds.`, {
        duration: 5000,
      });
    }

    // Handle 500 Server Error - show trace_id
    if (error.response?.status >= 500) {
      const traceId = error.response.data?.trace_id || 
                      error.response.headers?.['x-trace-id'];
      if (traceId) {
        toast.error(`Server error. Reference: ${traceId}`, {
          duration: 8000,
        });
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Handle authentication failure - clear tokens and redirect.
 */
function handleAuthFailure() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  delete apiClient.defaults.headers.common.Authorization;

  // Dispatch custom event for AuthContext to handle
  window.dispatchEvent(new CustomEvent('auth:logout'));
}

/**
 * Set authentication tokens.
 */
export function setAuthTokens(accessToken, refreshToken = null) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
  apiClient.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
}

/**
 * Clear authentication tokens.
 */
export function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  delete apiClient.defaults.headers.common.Authorization;
}

/**
 * Get stored refresh token.
 */
export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/**
 * Extract error details from an axios error response.
 * Backend returns: { detail: "...", trace_id: "..." }
 */
export function getErrorDetails(error) {
  const response = error?.response?.data;
  
  // Handle structured error responses (e.g., password policy)
  let message = response?.detail;
  if (typeof message === 'object' && message !== null) {
    message = message.message || JSON.stringify(message);
  }
  
  return {
    message: message || error?.message || 'An unexpected error occurred',
    traceId: response?.trace_id || error?.response?.headers?.['x-trace-id'] || null,
    status: error?.response?.status || null,
    errors: response?.detail?.errors || null,
  };
}

/**
 * Display an API error with trace_id for user reference.
 *
 * @param {Error} error - The axios error object
 * @param {string} fallbackMessage - Fallback message if error has no detail
 */
export function showApiError(error, fallbackMessage = 'Operation failed') {
  const { message, traceId, status, errors } = getErrorDetails(error);

  // Build the error message
  let displayMessage = message || fallbackMessage;

  // Show detailed errors if available (e.g., password policy violations)
  if (errors && Array.isArray(errors)) {
    displayMessage = errors.join('. ');
  }

  // Append trace_id if available for user reference
  if (traceId) {
    displayMessage = `${displayMessage} (Ref: ${traceId})`;
  }

  // Log full error details for debugging
  console.error('API Error:', {
    message,
    traceId,
    status,
    errors,
    fullError: error,
  });

  toast.error(displayMessage);

  return { message, traceId, status, errors };
}

/**
 * Create an error message with trace_id suitable for display.
 * Use this when you need the message string without showing a toast.
 *
 * @param {Error} error - The axios error object
 * @param {string} fallbackMessage - Fallback message if error has no detail
 * @returns {string} Formatted error message with trace_id
 */
export function formatApiError(error, fallbackMessage = 'Operation failed') {
  const { message, traceId, errors } = getErrorDetails(error);
  let displayMessage = message || fallbackMessage;

  if (errors && Array.isArray(errors)) {
    displayMessage = errors.join('. ');
  }

  if (traceId) {
    displayMessage = `${displayMessage} (Ref: ${traceId})`;
  }

  return displayMessage;
}

export { apiClient };
export default apiClient;
