package com.salmon.studion.domain.comment.repository;

import com.salmon.studion.domain.comment.entity.CommentMention;
import org.springframework.data.repository.query.Param;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface CommentMentionRepository extends JpaRepository<CommentMention, CommentMention.CommentMentionId> {

    @Query("""
        SELECT cm
        FROM CommentMention cm
        JOIN FETCH cm.user u
        WHERE cm.comment.id = :commentId
    """)
    List<CommentMention> findAllByCommentId(@Param("commentId") Integer commentId);

    void deleteAllByComment_Id(Integer commentId);

    void deleteAllByComment_IdIn(List<Integer> commentIds);

    @Query("""
        SELECT cm
        FROM CommentMention cm
        JOIN FETCH cm.user u
        WHERE cm.comment.id IN :commentIds
    """)
    List<CommentMention> findAllByCommentIds(@Param("commentIds") List<Integer> commentIds);
}
