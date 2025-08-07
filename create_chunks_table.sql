-- Create content_chunks table for better search functionality
-- Run this SQL in your MySQL database

CREATE TABLE IF NOT EXISTS content_chunks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    page_id INT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_type ENUM('title', 'heading', 'content') NOT NULL DEFAULT 'content',
    priority INT NOT NULL DEFAULT 5,
    chunk_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    FOREIGN KEY (page_id) REFERENCES scraped_pages(id) ON DELETE CASCADE,
    
    -- Indexes for better performance
    INDEX idx_page_id (page_id),
    INDEX idx_chunk_type (chunk_type),
    INDEX idx_priority (priority),
    INDEX idx_chunk_order (chunk_order),
    
    -- Full-text index for search
    FULLTEXT INDEX ft_chunk_text (chunk_text)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add some additional indexes for the existing scraped_pages table if not present
-- First check if columns exist, then add indexes
ALTER TABLE scraped_pages 
ADD INDEX IF NOT EXISTS idx_status (status),
ADD INDEX IF NOT EXISTS idx_url (url(255));

-- Only add created_at index if the column exists
-- ALTER TABLE scraped_pages ADD INDEX IF NOT EXISTS idx_created_at (created_at);

-- Optional: Add full-text index to existing scraped_pages if not present
-- ALTER TABLE scraped_pages ADD FULLTEXT INDEX ft_content_search (title, content, headings, meta_description, keywords);
