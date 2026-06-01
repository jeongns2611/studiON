package com.salmon.studion.domain.comment.dto.websocket;

import com.salmon.studion.domain.comment.dto.redis.CommentState;

public record CommentDeleteResponse (
        Integer projectId,
        Integer trackId,
        Integer commentId,
        Integer parentCommentId
) {
    public static CommentDeleteResponse of(Integer projectId, CommentState commentState) {
        return new CommentDeleteResponse(
                projectId,
                commentState.getTrackId(),
                commentState.getCommentId(),
                commentState.getParentCommentId()
        );
    }
}
