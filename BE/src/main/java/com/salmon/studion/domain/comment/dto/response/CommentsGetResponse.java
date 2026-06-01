package com.salmon.studion.domain.comment.dto.response;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.comment.dto.redis.CommentState;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

@Getter
public class CommentsGetResponse {

    private List<CommentDto> comments;

    public CommentsGetResponse(List<CommentDto> rootComments) {
        this.comments = rootComments;
    }

    public record CommentDto(
            Integer commentId,
            Integer trackId,
            Integer parentCommentId,
            String content,
            BigDecimal location,
            Boolean isResolved,
            UserSummary user,
            List<UserSummary> mentionedUsers,
            Instant createdAt,
            List<CommentDto> replies
    ) {
        public static CommentDto from(
                CommentState commentState,
                User user,
                List<UserSummary> mentionedUsers,
                List<CommentDto> replies
        ) {
            return new CommentDto(
                    commentState.getCommentId(),
                    commentState.getTrackId(),
                    commentState.getParentCommentId(),
                    commentState.getContent(),
                    commentState.getLocation(),
                    commentState.getIsResolved(),
                    UserSummary.from(user),
                    mentionedUsers,
                    commentState.getCreatedAt(),
                    replies
            );
        }
    }

    public record UserSummary(
            Integer userId,
            String nickname,
            String profileImgUrl
    ) {
        public static UserSummary from(User user) {
            return new UserSummary(user.getId(), user.getNickname(), user.getProfileImgUrl());
        }
    }

    public static CommentsGetResponse from(List<CommentDto> rootComments) {
        return new CommentsGetResponse(rootComments);
    }
}
