-- ============================================
-- PRODUCTS CATALOG DATABASE
-- (Aetos.Products repo)
-- ============================================

-- Products table
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,
    buy_price_min DECIMAL(10,2) NOT NULL,
    buy_price_max DECIMAL(10,2) NOT NULL,
    sell_target DECIMAL(10,2) NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(brand, model)
);

-- Product aliases (600d, rebel t3i, kiss x5)
CREATE TABLE product_aliases (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    alias VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fuzzy patterns (cannon 600d, canon 600 d)
CREATE TABLE product_fuzzy_patterns (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    pattern VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Matching filters (shared across all cameras)
CREATE TABLE filter_keywords (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(100) NOT NULL,
    filter_type VARCHAR(20) NOT NULL, -- 'reject' or 'boost'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(keyword, filter_type)
);

-- Indexes
CREATE INDEX idx_products_brand_model ON products(brand, model);
CREATE INDEX idx_products_active ON products(active);
CREATE INDEX idx_aliases_product ON product_aliases(product_id);
CREATE INDEX idx_fuzzy_product ON product_fuzzy_patterns(product_id);

-- Update trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();