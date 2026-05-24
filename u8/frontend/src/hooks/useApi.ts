import { useMemo } from 'react';
import { useAuth } from './useAuth';
import { ApiClient } from '../lib/api';

export function useApi(): ApiClient {
  const { getAccessToken } = useAuth();
  return useMemo(() => new ApiClient(getAccessToken), [getAccessToken]);
}
