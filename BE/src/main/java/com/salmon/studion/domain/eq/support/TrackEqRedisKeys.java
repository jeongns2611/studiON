package com.salmon.studion.domain.eq.support;

public class TrackEqRedisKeys {

    public static final long LOCK_TTL_SECONDS = 30L;
    public static final long DRAFT_TTL_SECONDS = 60L * 60L * 24L;

    private static final String LOCK_KEY_PATTERN = "project:%d:track-eq:%d:lock";
    private static final String DRAFT_KEY_PATTERN = "project:%d:track-eq:%d:draft";
    private static final String CURRENT_KEY_PATTERN = "project:%d:track:%d:eq:current";
    private static final String DELETED_TRACK_EQS_KEY_PATTERN = "project:%d:deleted_track_eq_tracks";

    private TrackEqRedisKeys() {

    }

    public static String lockKey(Integer projectId, Integer trackEqId) {
        return String.format(LOCK_KEY_PATTERN, projectId, trackEqId);
    }

    public static String draftKey(Integer projectId, Integer trackEqId) {
        return String.format(DRAFT_KEY_PATTERN, projectId, trackEqId);
    }

    public static String currentKey(Integer projectId, Integer trackId) {
        return String.format(CURRENT_KEY_PATTERN, projectId, trackId);
    }

    public static String deletedTrackEqsKey(Integer projectId) {
        return String.format(DELETED_TRACK_EQS_KEY_PATTERN, projectId);
    }
}
