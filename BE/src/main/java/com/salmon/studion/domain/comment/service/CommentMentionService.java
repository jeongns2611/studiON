package com.salmon.studion.domain.comment.service;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.comment.entity.Comment;
import com.salmon.studion.domain.comment.entity.CommentMention;
import com.salmon.studion.domain.comment.repository.CommentMentionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class CommentMentionService {

    private final CommentMentionRepository commentMentionRepository;

    /**
     * 저장 시 Redis의 코멘트 멘션 정보를 MySQL에 저장하는 메서드
     * @param comment
     * @param mentionUsers
     */
    @Transactional
    public void replaceCommentMentions(Comment comment, List<User> mentionUsers) {
        commentMentionRepository.deleteAllByComment_Id(comment.getId());

        if (mentionUsers == null || mentionUsers.isEmpty()) {
            return;
        }

        List<CommentMention> mentions = mentionUsers.stream()
                .map(user -> CommentMention.create(comment, user))
                .toList();

        commentMentionRepository.saveAll(mentions);
    }
    
}
