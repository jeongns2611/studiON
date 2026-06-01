package com.salmon.studion.domain.comment.entity;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.track.entity.Track;
import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.SQLRestriction;

import java.math.BigDecimal;
import java.time.Instant;

@Table(name = "comment")
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@SQLDelete(sql = "update comment set deleted_at = now() where id = ?")
@SQLRestriction("deleted_at is null")
public class Comment extends BaseEntity {

    @Id
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "track_id")
    private Track track;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    @Column(nullable = true)
    private Integer parentCommentId;

    @Column(nullable = false)
    private String content;

    @Column(nullable = false, precision = 11, scale = 7)
    private BigDecimal location;

    @Column(nullable = false)
    private Boolean isResolved = false;

    @Column(nullable = true)
    private Instant deletedAt;

    public static Comment create(
            Integer commentId,
            Track track,
            User user,
            Integer parentCommentId,
            String content,
            BigDecimal location,
            Boolean isResolved,
            Instant deletedAt
    ) {
        Comment comment = new Comment();
        comment.id = commentId;
        comment.track = track;
        comment.user = user;
        comment.parentCommentId = parentCommentId;
        comment.content = content;
        comment.location = location;
        comment.isResolved = isResolved != null ? isResolved : false;
        comment.deletedAt = deletedAt;
        return comment;
    }

    public void updateIsResolved() {
        this.isResolved = !this.isResolved;
    }

}
