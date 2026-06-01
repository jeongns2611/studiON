package com.salmon.studion.domain.comment.entity;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.io.Serializable;

@Table(name = "comment_mention")
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class CommentMention extends BaseEntity {
    @EmbeddedId
    private CommentMentionId id;

    @MapsId("commentId")
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "comment_id")
    private Comment comment;

    @MapsId("userId")
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    public static CommentMention create(Comment comment, User user) {
        CommentMention commentMention = new CommentMention();
        CommentMentionId id = new CommentMentionId();

        id.commentId = comment.getId();
        id.userId = user.getId();
        commentMention.id = id;
        commentMention.comment = comment;
        commentMention.user = user;

        return commentMention;
    }

    @Embeddable
    @EqualsAndHashCode
    @Getter
    @NoArgsConstructor
    public static class CommentMentionId implements Serializable {
        private Integer userId;
        private Integer commentId;
    }
}
