package com.salmon.studion.domain.comment.dto.websocket;

import com.salmon.studion.domain.comment.dto.redis.CommentState;

import java.time.Instant;

public record CommentStatusChangeResponse(
        Integer projectId,
        Integer trackId,
        Integer commentId,
        Integer parentCommentId,
        Boolean isResolved,
        Instant updatedAt
) {
    public static CommentStatusChangeResponse of(Integer projectId, CommentState commentState) {
        return new CommentStatusChangeResponse(
                projectId,
                commentState.getTrackId(),
                commentState.getCommentId(),
                commentState.getParentCommentId(),
                commentState.getIsResolved(),
                commentState.getUpdatedAt()
        );
    }
}
