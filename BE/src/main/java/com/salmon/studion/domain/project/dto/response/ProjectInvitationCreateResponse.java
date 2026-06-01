package com.salmon.studion.domain.project.dto.response;

import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.Instant;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class ProjectInvitationCreateResponse {
    private Integer projectId;
    private String inviteCode;
    private Instant expiresAt;

    public static ProjectInvitationCreateResponse of(
            Integer projectId,
            String inviteCode,
            Instant expiresAt
    ) {
        return new ProjectInvitationCreateResponse(projectId, inviteCode, expiresAt);
    }
}
