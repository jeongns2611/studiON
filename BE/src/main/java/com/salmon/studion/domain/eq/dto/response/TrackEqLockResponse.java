package com.salmon.studion.domain.eq.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TrackEqLockResponse {

    private Integer trackEqId;
    private Boolean isLocked;
    private Integer userId;
}
