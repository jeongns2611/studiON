package com.salmon.studion.domain.eq.dto.request;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public abstract class TrackEqRequest {

    private Integer projectId;

    public abstract void validate();
}
