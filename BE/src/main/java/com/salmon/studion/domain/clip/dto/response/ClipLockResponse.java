package com.salmon.studion.domain.clip.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ClipLockResponse {
    private Integer clipId;
    private Boolean isLocked;
    private Integer userId;
}
