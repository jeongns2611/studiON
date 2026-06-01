package com.salmon.studion.domain.clip.dto.request;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public abstract class ClipRequest {
    private Integer projectId;
    public abstract void validate();
}
