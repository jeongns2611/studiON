package com.salmon.studion.domain.comment.repository;

import com.querydsl.core.BooleanBuilder;
import com.querydsl.core.QueryFactory;
import com.querydsl.jpa.impl.JPAQueryFactory;
import com.salmon.studion.domain.auth.entity.QUser;
import com.salmon.studion.domain.comment.entity.Comment;
import com.salmon.studion.domain.comment.entity.QComment;
import com.salmon.studion.domain.comment.entity.QCommentMention;
import com.salmon.studion.domain.track.entity.QTrack;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
@RequiredArgsConstructor
public class CommentQueryRepositoryImpl implements CommentQueryRepository{

    private final JPAQueryFactory jpaQueryFactory;

    @Override
    public List<Comment> findComments(
            Integer projectId,
            Integer trackId,
            Boolean isResolved,
            boolean mentionedMe,
            Integer userId
    ) {
        QComment comment = QComment.comment;
        QUser user = QUser.user;
        QTrack track = QTrack.track;

        BooleanBuilder predicate = new BooleanBuilder();
        predicate.and(comment.track.project.id.eq(projectId));

        if (trackId != null) {
            predicate.and(comment.track.id.eq(trackId));
        }
        if (isResolved != null) {
            predicate.and(comment.isResolved.eq(isResolved));
        }

        var query = jpaQueryFactory
                .selectFrom(comment)
                .join(comment.user, user).fetchJoin()
                .join(comment.track, track). fetchJoin();

        if (mentionedMe) {
            QCommentMention mentionFilter = new QCommentMention("mentionFilter");
            query.join(mentionFilter)
                    .on(mentionFilter.comment.id.eq(comment.id), mentionFilter.id.userId.eq(userId));
        }

        return query
                .where(predicate)
                .orderBy(comment.track.id.asc(), comment.location.asc(), comment.createdAt.asc())
                .fetch();
    }

}
