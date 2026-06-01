package com.salmon.studion.domain.comment.repository;

import com.salmon.studion.domain.comment.entity.Comment;

import java.util.List;

public interface CommentQueryRepository {

    List<Comment> findComments(
            Integer projectId,
            Integer trackId,
            Boolean isResolved,
            boolean mentionedMe,
            Integer userId
    );
}
