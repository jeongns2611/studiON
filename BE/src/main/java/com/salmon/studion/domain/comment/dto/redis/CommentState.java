package com.salmon.studion.domain.comment.dto.redis;

import com.salmon.studion.domain.comment.entity.Comment;
import com.salmon.studion.global.common.enums.CommentDeleteReason;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

@Getter
@AllArgsConstructor
@NoArgsConstructor
public class CommentState {
    private Integer commentId;
    private Integer projectId;
    private Integer trackId;
    private Integer userId;
    private Integer parentCommentId;
    private String content;
    private BigDecimal location;
    private Boolean isResolved;
    private List<Integer> mentionedUserIds;
    private Instant createdAt;
    private Instant updatedAt;
    private Boolean deleted;
    private Instant deletedAt;
    private CommentDeleteReason deleteReason;

    public static CommentState create(
            Integer commentId,
            Integer projectId,
            Integer trackId,
            Integer userId,
            Integer parentCommentId,
            String content,
            BigDecimal location,
            List<Integer> mentionedUserIds,
            Instant now
    ) {
        return new CommentState(
                commentId,
                projectId,
                trackId,
                userId,
                parentCommentId,
                content,
                location,
                false,
                mentionedUserIds == null ? List.of() : mentionedUserIds,
                now,
                now,
                false,
                null,
                null
        );
    }

    public static CommentState toggleResolved(
            CommentState commentState,
            Instant updatedAt
    ) {
        return new CommentState(
                commentState.getCommentId(),
                commentState.getProjectId(),
                commentState.getTrackId(),
                commentState.getUserId(),
                commentState.getParentCommentId(),
                commentState.getContent(),
                commentState.getLocation(),
                !Boolean.TRUE.equals(commentState.getIsResolved()),
                commentState.getMentionedUserIds(),
                commentState.getCreatedAt(),
                updatedAt,
                commentState.getDeleted(),
                commentState.getDeletedAt(),
                commentState.getDeleteReason()
        );
    }

    public static CommentState markDeleted(
            CommentState commentState,
            CommentDeleteReason deleteReason,
            Instant deletedAt
    ) {
        return new CommentState(
                commentState.getCommentId(),
                commentState.getProjectId(),
                commentState.getTrackId(),
                commentState.getUserId(),
                commentState.getParentCommentId(),
                commentState.getContent(),
                commentState.getLocation(),
                commentState.getIsResolved(),
                commentState.getMentionedUserIds(),
                commentState.getCreatedAt(),
                commentState.getUpdatedAt(),
                true,
                deletedAt,
                deleteReason
        );
    }

    public static CommentState from(
            Comment comment,
            Integer projectId,
            List<Integer> mentionedUserIds
    ) {
        return new CommentState(
                comment.getId(),
                projectId,
                comment.getTrack().getId(),
                comment.getUser().getId(),
                comment.getParentCommentId(),
                comment.getContent(),
                comment.getLocation(),
                comment.getIsResolved(),
                mentionedUserIds,
                comment.getCreatedAt(),
                comment.getUpdatedAt(),
                false,
                comment.getDeletedAt(),
                null
        );
    }
}
