package com.salmon.studion.domain.project.dto.websocket;

import java.util.List;

public record ProjectOnlineUsersResponse(
        Integer projectId,
        List<ProjectOnlineUserResponse> users
) {
}
