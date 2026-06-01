package com.salmon.studion.domain.comment.repository;

import com.salmon.studion.domain.comment.entity.Comment;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.repository.query.Param;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface CommentRepository extends JpaRepository<Comment, Integer>, CommentQueryRepository {

    @Query("""
        SELECT c
        FROM Comment c
        JOIN FETCH c.user u
        JOIN FETCH c.track t
        WHERE c.id = :commentId
          AND t.project.id = :projectId
    """)
    Optional<Comment> findByIdAndProjectId(@Param("commentId") Integer commentId, @Param("projectId") Integer projectId);

    boolean existsByParentCommentIdAndDeletedAtIsNull(Integer commentId);

    @Query("""
        SELECT c
        FROM Comment c
        JOIN FETCH c.user
        JOIN FETCH c.track
        WHERE c.track.project.id = :projectId
    """)
    List<Comment> findAllByProjectId(@Param("projectId") Integer projectId);

    @Query("SELECT COALESCE(MAX(c.id), 0) FROM Comment c")
    Integer findMaxId();

    @Query("""
        SELECT c
        FROM Comment c
        JOIN FETCH c.user
        JOIN FETCH c.track
        WHERE c.id IN :commentIds
    """)
    List<Comment> findAllByIdInWithUserAndTrack(@Param("commentIds") List<Integer> commentIds);

    @Query("""
        SELECT c
        FROM Comment c
        JOIN FETCH c.user
        JOIN FETCH c.track
        WHERE c.track.id IN :trackIds
    """)
    List<Comment> findAllByTrackIds(@Param("trackIds") List<Integer> trackIds);

    @Modifying
    @Query("DELETE FROM Comment c WHERE c.id IN :commentIds")
    void deleteAllByIds(@Param("commentIds") List<Integer> commentIds);

    @Modifying
    @Query("DELETE FROM Comment c WHERE c.track.id IN :trackIds")
    void deleteAllByTrackIds(@Param("trackIds") List<Integer> trackIds);
}
