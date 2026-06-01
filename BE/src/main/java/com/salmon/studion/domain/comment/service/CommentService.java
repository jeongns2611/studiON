package com.salmon.studion.domain.comment.service;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.repository.UserRepository;
import com.salmon.studion.domain.comment.dto.redis.CommentState;
import com.salmon.studion.domain.comment.entity.Comment;
import com.salmon.studion.domain.comment.entity.CommentMention;
import com.salmon.studion.domain.comment.repository.CommentMentionRepository;
import com.salmon.studion.domain.comment.repository.CommentRedisRepository;
import com.salmon.studion.domain.comment.repository.CommentRepository;
import com.salmon.studion.domain.project.service.ProjectDirtyStateService;
import com.salmon.studion.domain.track.repository.TrackRepository;
import com.salmon.studion.global.common.enums.CommentDeleteReason;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Clock;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CommentService {

    private final CommentRedisRepository commentRedisRepository;
    private final CommentRepository commentRepository;
    private final CommentMentionRepository commentMentionRepository;
    private final CommentMentionService commentMentionService;
    private final TrackRepository trackRepository;
    private final UserRepository userRepository;
    private final ProjectDirtyStateService projectDirtyStateService;
    private final Clock clock;

    @Transactional
    public CommentState  createComment(
            Integer projectId,
            Integer trackId,
            User user,
            Integer parentCommentId,
            String content,
            BigDecimal location,
            List<Integer> mentionedUserIds
    ) {
        Integer commentId = commentRedisRepository.nextCommentId();
        java.time.Instant now = clock.instant();

        CommentState commentState = CommentState.create(
                commentId,
                projectId,
                trackId,
                user.getId(),
                parentCommentId,
                content,
                location,
                mentionedUserIds,
                now
        );

        commentRedisRepository.save(commentState);
        return commentState;
    }

    @Transactional(readOnly = true)
    public CommentState getCommentByProjectId(Integer commentId, Integer projectId) {
        if (projectDirtyStateService.isDirty(projectId) || commentRedisRepository.hasWorkingSet(projectId)) {
            CommentState commentState = commentRedisRepository.getOrLoad(projectId, commentId);

            if (Boolean.TRUE.equals(commentState.getDeleted())) {
                throw new BusinessException(ErrorCode.COMMENT_NOT_FOUND);
            }

            return commentState;
        }

        Comment comment = commentRepository.findByIdAndProjectId(commentId, projectId)
                .orElseThrow(() -> new BusinessException(ErrorCode.COMMENT_NOT_FOUND));

        Map<Integer, List<Integer>> mentionUserIdsByCommentId =
                loadMentionUserIdsByCommentIds(List.of(comment.getId()));

        return CommentState.from(
                comment,
                projectId,
                mentionUserIdsByCommentId.getOrDefault(comment.getId(), List.of())
        );
    }

    @Transactional(readOnly = true)
    public List<CommentState> getComments(
            Integer projectId,
            Integer trackId,
            Boolean isResolved,
            boolean mentionedMe,
            Integer userId
    ) {
        boolean useWorkingSet = projectDirtyStateService.isDirty(projectId) || commentRedisRepository.hasWorkingSet(projectId);

        if (useWorkingSet) {
            return commentRedisRepository.findAllOrLoadByProjectId(projectId).stream()
                    .filter(commentState -> !Boolean.TRUE.equals(commentState.getDeleted()))
                    .filter(commentState -> trackId == null || trackId.equals(commentState.getTrackId()))
                    .filter(commentState -> isResolved == null || isResolved.equals(commentState.getIsResolved()))
                    .filter(commentState -> !mentionedMe || commentState.getMentionedUserIds().stream().anyMatch(id -> id.equals(userId)))
                    .toList();
        }

        List<Comment> comments = commentRepository.findComments(projectId, trackId, isResolved, mentionedMe, userId);
        if (comments.isEmpty()) {
            return List.of();
        }

        Map<Integer, List<Integer>> mentionUserIdsByCommentId =
                loadMentionUserIdsByCommentIds(comments.stream().map(Comment::getId).toList());

        return comments.stream()
                .map(comment -> CommentState.from(
                        comment,
                        projectId,
                        mentionUserIdsByCommentId.getOrDefault(comment.getId(), List.of())
                ))
                .toList();
    }

    @Transactional(readOnly = true)
    public boolean hasCommentWorkingSet(Integer projectId) {
        return commentRedisRepository.hasWorkingSet(projectId);
    }

    @Transactional
    public CommentState changeResolved(CommentState commentState) {
        CommentState updatedState = CommentState.toggleResolved(commentState, clock.instant());

        commentRedisRepository.save(updatedState);
        return updatedState;
    }

    @Transactional
    public void deleteCommentsByTrack(Integer projectId, Integer trackId) {
        commentRedisRepository.markDeletedByTrack(projectId, trackId, clock.instant());
    }

    @Transactional
    public void deleteComment(Integer projectId, Integer commentId) {
        commentRedisRepository.markDeletedCascadeByParent(projectId, commentId, clock.instant());
    }

    @Transactional(readOnly = true)
    public boolean hasActiveChildren(Integer projectId, Integer commentId) {
        if (projectDirtyStateService.isDirty(projectId) || commentRedisRepository.hasWorkingSet(projectId)) {
            return commentRedisRepository.findAllOrLoadByProjectId(projectId).stream()
                    .anyMatch(commentState ->
                            commentId.equals(commentState.getParentCommentId())
                                    && !Boolean.TRUE.equals(commentState.getDeleted()));
        }

        return commentRepository.existsByParentCommentIdAndDeletedAtIsNull(commentId);
    }

    /**
     * 저장 시점에 deleted 처리된 comment를 MySQL에 반영하는 메서드
     * @param projectId
     *  - DIRECT / PARENT_CASCADE: soft delete
     *  - TRACK_DELETE: hard delete
     */
    @Transactional
    public void deleteRemovedCommentsFromMysql(Integer projectId) {
        Set<Integer> deletedCommentIds = commentRedisRepository.getDeletedCommentIds(projectId);
        if (deletedCommentIds.isEmpty()) {
            return;
        }

        List<CommentState> deletedStates = deletedCommentIds.stream()
                .map(commentId -> commentRedisRepository.findByProjectIdAndCommentId(projectId, commentId).orElse(null))
                .filter(Objects::nonNull)
                .toList();

        if (deletedStates.isEmpty()) {
            return;
        }

        List<Integer> softDeleteIds = deletedStates.stream()
                .filter(state -> state.getDeleteReason() != CommentDeleteReason.TRACK_DELETE)
                .map(CommentState::getCommentId)
                .toList();

        List<Integer> hardDeleteIds = deletedStates.stream()
                .filter(state -> state.getDeleteReason() == CommentDeleteReason.TRACK_DELETE)
                .map(CommentState::getCommentId)
                .toList();

        if (!softDeleteIds.isEmpty()) {
            List<Comment> softDeleteTargets = commentRepository.findAllByIdInWithUserAndTrack(softDeleteIds);
            commentMentionRepository.deleteAllByComment_IdIn(softDeleteIds);
            commentRepository.deleteAll(softDeleteTargets);
        }

        if (!hardDeleteIds.isEmpty()) {
            commentMentionRepository.deleteAllByComment_IdIn(hardDeleteIds);
            commentRepository.deleteAllByIds(hardDeleteIds);
        }
    }
    
    /**
     * 저장 시점에 Redis에 있는 Comment를 MySQL에 반영하는 메서드
     * @param projectId
     */
    @Transactional
    public void upsertCommentsFromRedis(Integer projectId) {
        List<CommentState> activeStates = getActiveCommentStates(projectId);
        if (activeStates.isEmpty()) {
            return;
        }

        List<Comment> commentsToSave = activeStates.stream()
                .map(this::toCommentEntity)
                .toList();

        commentRepository.saveAll(commentsToSave);
    }
    
    /**
     * 저장 시점에 Redis에 있는 CommentMention을 MySQL에 반영하는 메서드
     * @param projectId
     */
    @Transactional
    public void replaceCommentMentionsFromRedis(Integer projectId) {
        List<CommentState> activeStates = getActiveCommentStates(projectId);
        if (activeStates.isEmpty()) {
            return;
        }

        List<Integer> commentIds = activeStates.stream()
                .map(CommentState::getCommentId)
                .toList();

        Map<Integer, Comment> commentsById = commentRepository.findAllByIdInWithUserAndTrack(commentIds).stream()
                .collect(Collectors.toMap(Comment::getId, comment -> comment));

        List<Integer> mentionedUserIds = activeStates.stream()
                .flatMap(state -> state.getMentionedUserIds().stream())
                .distinct()
                .toList();

        Map<Integer, User> usersById = userRepository.findAllById(mentionedUserIds).stream()
                .collect(Collectors.toMap(User::getId, user -> user));

        for (CommentState state : activeStates) {
            Comment comment = commentsById.get(state.getCommentId());
            if (comment == null) {
                continue;
            }

            List<User> mentionUsers = state.getMentionedUserIds().stream()
                    .map(usersById::get)
                    .filter(Objects::nonNull)
                    .toList();

            commentMentionService.replaceCommentMentions(comment, mentionUsers);
        }
    }

    @Transactional
    public void clearDeletedCommentKeys(Integer projectId) {
        commentRedisRepository.clearDeletedCommentIds(projectId);
    }

    private List<CommentState> getActiveCommentStates(Integer projectId) {
        return commentRedisRepository.findAllOrLoadByProjectId(projectId).stream()
                .filter(state -> !Boolean.TRUE.equals(state.getDeleted()))
                .toList();
    }

    private Comment toCommentEntity(CommentState commentState) {
        return Comment.create(
                commentState.getCommentId(),
                trackRepository.getReferenceById(commentState.getTrackId()),
                userRepository.getReferenceById(commentState.getUserId()),
                commentState.getParentCommentId(),
                commentState.getContent(),
                commentState.getLocation(),
                commentState.getIsResolved(),
                commentState.getDeletedAt()
        );
    }

    private Map<Integer, List<Integer>> loadMentionUserIdsByCommentIds(List<Integer> commentIds) {
        if (commentIds.isEmpty()) {
            return Map.of();
        }

        List<CommentMention> mentions = commentMentionRepository.findAllByCommentIds(commentIds);

        return mentions.stream()
                .collect(Collectors.groupingBy(
                        mention -> mention.getComment().getId(),
                        Collectors.mapping(mention -> mention.getUser().getId(), Collectors.toList())
                ));
    }

}
