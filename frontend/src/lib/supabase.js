import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.REACT_APP_SUPABASE_URL || 'https://placeholder.supabase.co';
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY || 'placeholder-key';

// Only create real client if properly configured
let supabase = null;

try {
  if (supabaseUrl && supabaseAnonKey && supabaseUrl.includes('supabase.co') && !supabaseUrl.includes('placeholder')) {
    supabase = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
    });
  }
} catch (error) {
  console.warn('Supabase client creation failed:', error);
}

// Check if Supabase is configured
export const isSupabaseConfigured = () => {
  return supabase !== null && 
         process.env.REACT_APP_SUPABASE_URL && 
         !process.env.REACT_APP_SUPABASE_URL.includes('placeholder');
};

// Export a mock client for when Supabase is not configured
export { supabase };
