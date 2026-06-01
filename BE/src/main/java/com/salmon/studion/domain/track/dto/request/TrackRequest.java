package com.salmon.studion.domain.track.dto.request;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public abstract class TrackRequest {
    private Integer projectId;
    public abstract void validate();
}
