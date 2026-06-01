package com.salmon.studion.domain.project.dto.redis;

import java.time.Instant;

public record ProjectInviteRedisValue (
        Integer projectId,
        String inviteCode,
        Integer createdBy,
        Instant expiresAt
) {
    public boolean isExpired(Instant now) {
        return expiresAt.isBefore(now);
    }
}
