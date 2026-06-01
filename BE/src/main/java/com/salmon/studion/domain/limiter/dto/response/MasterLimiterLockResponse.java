package com.salmon.studion.domain.limiter.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class MasterLimiterLockResponse {

    private Integer masterLimiterId;
    private Boolean isLocked;
    private Integer userId;
}
