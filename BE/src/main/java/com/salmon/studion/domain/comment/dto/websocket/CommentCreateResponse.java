package com.salmon.studion.domain.comment.dto.websocket;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.comment.dto.redis.CommentState;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public record CommentCreateResponse(
        Integer projectId,
        Integer trackId,
        Integer commentId,
        Integer parentCommentId,
        String content,
        BigDecimal location,    // 댓글이 달린 마디 위치
        Boolean isResolved,

        UserSummary author,
        List<UserSummary> mentionedUsers,
        Instant createdAt
) {
    public record UserSummary(
            Integer userId,
            String nickname,
            String profileImgUrl
    ) {
        public static UserSummary from(User user) {
            return new UserSummary(
                    user.getId(),
                    user.getNickname(),
                    user.getProfileImgUrl());
        }
    }

    public static CommentCreateResponse of(
            Integer projectId,
            CommentState commentState,
            User user,
            List<User> mentionedUsers) {
        return new CommentCreateResponse(
                projectId,
                commentState.getTrackId(),
                commentState.getCommentId(),
                commentState.getParentCommentId(),
                commentState.getContent(),
                commentState.getLocation(),
                commentState.getIsResolved(),
                UserSummary.from(user),
                mentionedUsers.stream()
                        .map(UserSummary::from)
                        .toList(),
                commentState.getCreatedAt()
        );
    }
}
