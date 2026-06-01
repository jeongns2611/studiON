package com.salmon.studion.domain.comment.dto.websocket;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@NoArgsConstructor
public abstract class CommentRequest {
    @Setter
    private Integer projectId;

    public abstract void validate();
}
