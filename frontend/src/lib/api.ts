/**
 * FinSight AI — Client API Configuration
 * =====================================
 * Single source of truth for backend endpoints across local & production deployments.
 */

export const API_BASE_URL: string = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Base backend URL stripped of trailing slashes or /api subpath
export const BACKEND_URL: string = API_BASE_URL.replace(/\/api\/?$/, '').replace(/\/$/, '');

// Canonical /api endpoint prefix
export const API_BASE: string = `${BACKEND_URL}/api`;
