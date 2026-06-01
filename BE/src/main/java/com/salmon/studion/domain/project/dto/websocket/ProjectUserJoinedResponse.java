package com.salmon.studion.domain.project.dto.websocket;

public record ProjectUserJoinedResponse(
        Integer projectId,
        ProjectOnlineUserResponse user
) {
}
