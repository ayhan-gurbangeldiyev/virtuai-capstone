-- Migration 004: Content Evolution
-- Adds evolution/iterate support to generations table

-- Parent reference: which generation was this evolved from
ALTER TABLE generations ADD COLUMN IF NOT EXISTS parent_generation_id UUID REFERENCES generations(id) ON DELETE SET NULL;

-- Which variant indices were selected for evolution
ALTER TABLE generations ADD COLUMN IF NOT EXISTS parent_variant_indices INT[] DEFAULT '{}';

-- User's free-text feedback for evolution direction
ALTER TABLE generations ADD COLUMN IF NOT EXISTS evolution_feedback TEXT;

-- Quick tags selected by user (e.g. ["shorter", "bolder"])
ALTER TABLE generations ADD COLUMN IF NOT EXISTS evolution_quick_tags TEXT[] DEFAULT '{}';

-- Depth in the evolution chain (0 = original, 1 = first evolve, etc.)
ALTER TABLE generations ADD COLUMN IF NOT EXISTS evolution_depth INT DEFAULT 0;

-- Chain ID groups all generations in the same evolution thread
ALTER TABLE generations ADD COLUMN IF NOT EXISTS evolution_chain_id UUID;

-- Indexes for efficient chain queries
CREATE INDEX IF NOT EXISTS idx_gen_chain ON generations(evolution_chain_id) WHERE evolution_chain_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gen_parent ON generations(parent_generation_id) WHERE parent_generation_id IS NOT NULL;
