import { supabase } from '../lib/supabase';
import { createSessionCoordinator } from './sessionCoordinator';

export const authSession = createSessionCoordinator(supabase.auth);
