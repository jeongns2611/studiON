package com.salmon.studion.domain.project.dto.response;

import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class ProjectInvitationAcceptResponse {
    private Integer projectId;

    public static ProjectInvitationAcceptResponse of(Integer projectId) {
        return new ProjectInvitationAcceptResponse(projectId);
    }
}
