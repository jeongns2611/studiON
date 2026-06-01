package com.salmon.studion.domain.limiter.support;

public final class LimiterRedisKeys {

    public static final long LOCK_TTL_SECONDS = 30L;
    public static final long DRAFT_TTL_SECONDS = 60L * 60L * 24L;

    private static final String LOCK_KEY_PATTERN = "project:%d:master-limiter:lock";
    private static final String DRAFT_KEY_PATTERN = "project:%d:master-limiter:draft";
    private static final String CURRENT_KEY_PATTERN = "project:%d:master-limiter:current";

    private LimiterRedisKeys() {
    }

    public static String lockKey(Integer projectId) {
        return String.format(LOCK_KEY_PATTERN, projectId);
    }

    public static String draftKey(Integer projectId) {
        return String.format(DRAFT_KEY_PATTERN, projectId);
    }

    public static String currentKey(Integer projectId) {
        return String.format(CURRENT_KEY_PATTERN, projectId);
    }
}
