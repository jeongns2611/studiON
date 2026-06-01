CREATE TABLE IF NOT EXISTS position_group (
    code INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    `order` INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS position_detail (
    code INT NOT NULL,
    group_code INT NULL,
    name VARCHAR(50) NOT NULL,
    `order` INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (code),
    KEY idx_position_detail_group_code (group_code),
    CONSTRAINT fk_position_detail_group
        FOREIGN KEY (group_code) REFERENCES position_group (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user` (
    id INT NOT NULL AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    provider_id VARCHAR(100) NOT NULL,
    profile_img_url VARCHAR(255) NULL,
    nickname VARCHAR(20) NOT NULL,
    last_login_at TIMESTAMP NULL,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS project (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    root_note VARCHAR(10) NOT NULL,
    mode VARCHAR(10) NOT NULL,
    tempo DOUBLE NOT NULL,
    time_sig_numerator INT NOT NULL,
    time_sig_denominator INT NOT NULL,
    total_bar_count INT NOT NULL,
    total_play_time_ms INT NOT NULL,
    track_count INT NOT NULL,
    total_audio_size_byte BIGINT NOT NULL,
    deleted_at TIMESTAMP NULL,
    last_update_at TIMESTAMP NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audio_metadata (
    id INT NOT NULL AUTO_INCREMENT,
    object_key VARCHAR(1024) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(255) NULL,
    size_bytes INT NOT NULL,
    duration_ms INT NOT NULL,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dm_room (
    id INT NOT NULL AUTO_INCREMENT,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ai_analysis_job (
    id INT NOT NULL AUTO_INCREMENT,
    project_id INT NOT NULL,
    requested_by INT NULL,
    dispatch_type VARCHAR(50) NULL,
    status VARCHAR(50) NOT NULL,
    phase VARCHAR(100) NOT NULL,
    current_node VARCHAR(100) NULL,
    progress INT NOT NULL,
    queue_name VARCHAR(100) NULL,
    timeline_snapshot_id VARCHAR(255) NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    error_code VARCHAR(100) NULL,
    error_message VARCHAR(1000) NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS master_track (
    project_id INT NOT NULL,
    is_soloed BIT NOT NULL,
    is_muted BIT NOT NULL,
    volume DOUBLE NOT NULL,
    pan INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (project_id),
    CONSTRAINT fk_master_track_project
        FOREIGN KEY (project_id) REFERENCES project (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS track (
    id INT NOT NULL,
    project_id INT NOT NULL,
    pre_track_id INT NULL,
    post_track_id INT NULL,
    track_type VARCHAR(255) NOT NULL,
    name VARCHAR(255) NULL,
    is_soloed BIT NOT NULL,
    is_muted BIT NOT NULL,
    volume DOUBLE NOT NULL,
    pan INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id),
    KEY idx_track_project_id (project_id),
    CONSTRAINT fk_track_project
        FOREIGN KEY (project_id) REFERENCES project (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS clip (
    id INT NOT NULL,
    track_id INT NOT NULL,
    audio_metadata_id INT NOT NULL,
    color VARCHAR(7) NOT NULL,
    `start` DOUBLE NOT NULL,
    duration DOUBLE NOT NULL,
    audio_start_ms INT NOT NULL,
    audio_duration_ms INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id),
    KEY idx_clip_track_id (track_id),
    KEY idx_clip_audio_metadata_id (audio_metadata_id),
    CONSTRAINT fk_clip_track
        FOREIGN KEY (track_id) REFERENCES track (id),
    CONSTRAINT fk_clip_audio_metadata
        FOREIGN KEY (audio_metadata_id) REFERENCES audio_metadata (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS comment (
    id INT NOT NULL,
    track_id INT NULL,
    user_id INT NULL,
    parent_comment_id INT NULL,
    content VARCHAR(255) NOT NULL,
    location DECIMAL(11, 7) NOT NULL,
    is_resolved BIT NOT NULL,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id),
    KEY idx_comment_track_id (track_id),
    KEY idx_comment_user_id (user_id),
    CONSTRAINT fk_comment_track
        FOREIGN KEY (track_id) REFERENCES track (id),
    CONSTRAINT fk_comment_user
        FOREIGN KEY (user_id) REFERENCES `user` (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS comment_mention (
    user_id INT NOT NULL,
    comment_id INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (user_id, comment_id),
    KEY idx_comment_mention_comment_id (comment_id),
    CONSTRAINT fk_comment_mention_user
        FOREIGN KEY (user_id) REFERENCES `user` (id),
    CONSTRAINT fk_comment_mention_comment
        FOREIGN KEY (comment_id) REFERENCES comment (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_position (
    user_id INT NOT NULL,
    position_code INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (user_id, position_code),
    KEY idx_user_position_position_code (position_code),
    CONSTRAINT fk_user_position_user
        FOREIGN KEY (user_id) REFERENCES `user` (id),
    CONSTRAINT fk_user_position_position_detail
        FOREIGN KEY (position_code) REFERENCES position_detail (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dm_room_member (
    id INT NOT NULL AUTO_INCREMENT,
    dm_room_id INT NULL,
    user_id INT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_dm_room_member_user_room (user_id, dm_room_id),
    KEY idx_dm_room_member_room_id (dm_room_id),
    CONSTRAINT fk_dm_room_member_room
        FOREIGN KEY (dm_room_id) REFERENCES dm_room (id),
    CONSTRAINT fk_dm_room_member_user
        FOREIGN KEY (user_id) REFERENCES `user` (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS project_member (
    id INT NOT NULL AUTO_INCREMENT,
    project_id INT NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_project_member_project_user (project_id, user_id),
    KEY idx_project_member_user_id (user_id),
    CONSTRAINT fk_project_member_project
        FOREIGN KEY (project_id) REFERENCES project (id),
    CONSTRAINT fk_project_member_user
        FOREIGN KEY (user_id) REFERENCES `user` (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS project_master_audio_version (
    id INT NOT NULL AUTO_INCREMENT,
    project_id INT NOT NULL,
    audio_metadata_id INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    memo VARCHAR(255) NULL,
    status VARCHAR(255) NULL,
    failed_reason VARCHAR(1000) NULL,
    render_snapshot_json LONGTEXT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_project_master_audio_version_audio_metadata (audio_metadata_id),
    KEY idx_project_master_audio_version_project_id (project_id),
    CONSTRAINT fk_project_master_audio_version_project
        FOREIGN KEY (project_id) REFERENCES project (id),
    CONSTRAINT fk_project_master_audio_version_audio_metadata
        FOREIGN KEY (audio_metadata_id) REFERENCES audio_metadata (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS master_limiter (
    id INT NOT NULL AUTO_INCREMENT,
    project_id INT NOT NULL,
    is_enabled BIT NOT NULL,
    threshold_db DOUBLE NOT NULL,
    ceiling_dbfs DOUBLE NOT NULL,
    attack_ms DOUBLE NOT NULL,
    release_ms DOUBLE NOT NULL,
    input_gain_db DOUBLE NOT NULL,
    makeup_gain_db DOUBLE NOT NULL,
    job_id INT NULL,
    suggestion_action_id INT NULL,
    applied_suggestion_id INT NULL,
    source_type_code INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_master_limiter_project_id (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS track_eq (
    id INT NOT NULL AUTO_INCREMENT,
    track_id INT NOT NULL,
    project_id INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS track_eq_band (
    id INT NOT NULL AUTO_INCREMENT,
    track_eq_id INT NOT NULL,
    band_order INT NOT NULL,
    eq_type_code INT NOT NULL,
    frequency_hz INT NOT NULL,
    q DOUBLE NOT NULL,
    gain_delta_db DOUBLE NOT NULL,
    job_id INT NULL,
    suggestion_action_id INT NULL,
    applied_suggestion_id INT NULL,
    source_type_code INT NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT NULL,
    updated_by INT NULL,
    PRIMARY KEY (id),
    KEY idx_track_eq_band_track_eq_id (track_eq_id),
    CONSTRAINT fk_track_eq_band_track_eq
        FOREIGN KEY (track_eq_id) REFERENCES track_eq (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
