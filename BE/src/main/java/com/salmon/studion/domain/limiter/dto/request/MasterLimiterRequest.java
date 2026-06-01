package com.salmon.studion.domain.limiter.dto.request;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public abstract class MasterLimiterRequest {

    private Integer projectId;

    public abstract void validate();
}
