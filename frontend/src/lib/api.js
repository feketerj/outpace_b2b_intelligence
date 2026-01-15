/**
 * API utilities with trace_id error handling.
 *
 * Usage:
 *   import { showApiError } from '../lib/api';
 *
 *   catch (error) {
 *     showApiError(error, 'Failed to save user');
 *   }
 *
 * This extracts trace_id from backend error responses and displays it
 * so users can reference it when reporting issues.
 */

import { toast } from 'sonner';

/**
 * Extract error details from an axios error response.
 * Backend returns: { detail: "...", trace_id: "..." }
 */
export function getErrorDetails(error) {
  const response = error?.response?.data;
  return {
    message: response?.detail || error?.message || 'An unexpected error occurred',
    traceId: response?.trace_id || error?.response?.headers?.['x-trace-id'] || null,
    status: error?.response?.status || null,
  };
}

/**
 * Display an API error with trace_id for user reference.
 *
 * @param {Error} error - The axios error object
 * @param {string} fallbackMessage - Fallback message if error has no detail
 */
export function showApiError(error, fallbackMessage = 'Operation failed') {
  const { message, traceId, status } = getErrorDetails(error);

  // Build the error message
  let displayMessage = message || fallbackMessage;

  // Append trace_id if available for user reference
  if (traceId) {
    displayMessage = `${displayMessage} (Ref: ${traceId})`;
  }

  // Log full error details for debugging
  console.error('API Error:', {
    message,
    traceId,
    status,
    fullError: error,
  });

  toast.error(displayMessage);

  return { message, traceId, status };
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
  const { message, traceId } = getErrorDetails(error);
  let displayMessage = message || fallbackMessage;

  if (traceId) {
    displayMessage = `${displayMessage} (Ref: ${traceId})`;
  }

  return displayMessage;
}
