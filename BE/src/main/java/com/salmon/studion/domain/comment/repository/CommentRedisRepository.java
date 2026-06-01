package com.salmon.studion.domain.comment.repository;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.comment.dto.redis.CommentState;
import com.salmon.studion.domain.comment.entity.Comment;
import com.salmon.studion.domain.comment.entity.CommentMention;
import com.salmon.studion.global.common.enums.CommentDeleteReason;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.*;
import java.util.function.Function;
import java.util.stream.Collectors;

@Repository
@RequiredArgsConstructor
public class CommentRedisRepository {

    private static final String COMMENTS_KEY = "project:%d:comments";
    private static final String DELETED_COMMENTS_KEY = "project:%d:deleted_comments";
    private static final String COMMENT_ID_SEQ_KEY = "global:comment:id_seq";

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final CommentRepository commentRepository;
    private final CommentMentionRepository commentMentionRepository;

    /**
     * 다음 코멘트의 ID를 발급
     * @return
     */
    public Integer nextCommentId() {
        initializeCommentIdSequenceIfNeeded();

        Long nextId = redisTemplate.opsForValue().increment(COMMENT_ID_SEQ_KEY);
        if (nextId == null) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR, "Next Comment Id 발급중 에러 발생");
        }

        return nextId.intValue();
    }

    /**
     * comment 1개를 Redis에 저장
     * @param commentState
     */
    public void save(CommentState commentState) {
        try {
            redisTemplate.opsForHash().put(
                    commentsKey(commentState.getProjectId()),
                    String.valueOf(commentState.getCommentId()),
                    objectMapper.writeValueAsString(commentState)
            );
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR, "Comment를 Redis에 저장중 에러 발생");
        }
    }

    /**
     * comment 여러 개를 Redis에 저장
     * @param commentStateList
     */
    public void saveAll(List<CommentState> commentStateList) {
        commentStateList.forEach(this::save);
    }

    /**
     * comment 1개를 Redis에서 조회
     * @param projectId
     * @param commentId
     * @return
     */
    public Optional<CommentState> findByProjectIdAndCommentId(Integer projectId, Integer commentId) {
        String json = (String) redisTemplate.opsForHash().get(commentsKey(projectId), String.valueOf(commentId));

        if (json == null) {
            return Optional.empty();
        }
        return Optional.of(readCommentState(json));
    }

    /**
     * comment 1개 조회 (fallback 조회)
     * @param projectId
     * @param commentId
     * @return
     */
    public CommentState getOrLoad(Integer projectId, Integer commentId) {
        return findByProjectIdAndCommentId(projectId, commentId)
                .orElseGet(() -> loadSingleFromMysql(projectId, commentId));
    }

    /**
     * comment 여러 개를 Redis에서 조회
     * @param projectId
     * @return
     */
    public List<CommentState> findAllByProjectId(Integer projectId) {
        Map<Object, Object> entries = redisTemplate.opsForHash().entries(commentsKey(projectId));

        if (entries.isEmpty()) {
            return List.of();
        }

        return entries.values().stream()
                .map(String.class::cast)
                .map(this::readCommentState)
                .sorted(defaultOrder())
                .toList();
    }

    /**
     * comment 여러 개 조회 (fallback 조회)
     * @param projectId
     * @return
     */
    public List<CommentState> findAllOrLoadByProjectId(Integer projectId) {
        Map<Integer, CommentState> mergedStates = new HashMap<>();

        loadAllFromMysql(projectId).forEach(state -> mergedStates.put(state.getCommentId(), state));
        findAllByProjectId(projectId).forEach(state -> mergedStates.put(state.getCommentId(), state));

        return mergedStates.values().stream()
                .sorted(defaultOrder())
                .toList();
    }

    /**
     * comment 삭제 마킹
     * @param projectId
     * @param commentId
     * @param deleteReason
     * @param deletedAt
     */
    public void markDeleted(
            Integer projectId,
            Integer commentId,
            CommentDeleteReason deleteReason,
            Instant deletedAt
    ) {
        CommentState commentState = getOrLoad(projectId, commentId);

        CommentState deletedState = CommentState.markDeleted(commentState, deleteReason, deletedAt);

        save(deletedState);

        addDeletedCommentId(projectId, commentId);
    }

    /**
     * comment 삭제 마킹 (부모 comment가 삭제된 경우)
     * @param projectId
     * @param parentCommentId
     * @param deletedAt
     */
    public void markDeletedCascadeByParent(
            Integer projectId,
            Integer parentCommentId,
            Instant deletedAt
    ) {
        List<CommentState> states = findAllOrLoadByProjectId(projectId);

        states.stream()
                .filter(state -> parentCommentId.equals(state.getCommentId()) || isDescendantOf(states, state, parentCommentId))
                .filter(state -> !Boolean.TRUE.equals(state.getDeleted()))
                .forEach(state -> {
                    CommentDeleteReason reason = parentCommentId.equals(state.getCommentId())
                            ? CommentDeleteReason.DIRECT
                            : CommentDeleteReason.PARENT_CASCADE;
                    markDeleted(projectId, state.getCommentId(), reason, deletedAt);
                });
    }

    /**
     * comment 삭제 마킹 (Track이 삭제된 경우)
     * @param projectId
     * @param trackId
     * @param deletedAt
     */
    public void markDeletedByTrack(
            Integer projectId,
            Integer trackId,
            Instant deletedAt
    ) {
        List<CommentState> states = findAllOrLoadByProjectId(projectId);

        states.stream()
                .filter(state -> trackId.equals(state.getTrackId()))
                .filter(state -> !Boolean.TRUE.equals(state.getDeleted()))
                .forEach(state -> markDeleted(
                        projectId,
                        state.getCommentId(),
                        CommentDeleteReason.TRACK_DELETE,
                        deletedAt
                ));
    }

    /**
     * 삭제 마킹된 comment Id 목록 조회
     * @param projectId
     * @return
     */
    public Set<Integer> getDeletedCommentIds(Integer projectId) {
        Set<String> members = redisTemplate.opsForSet().members(deletedCommentsKey(projectId));

        if (members == null || members.isEmpty()) {
            return Set.of();
        }

        return members.stream().map(Integer::parseInt).collect(Collectors.toSet());
    }

    /**
     * deleted set 에 삭제할 comment Id 추가
     * @param projectId
     * @param commentId
     */
    public void addDeletedCommentId(Integer projectId, Integer commentId) {
        redisTemplate.opsForSet().add(deletedCommentsKey(projectId), String.valueOf(commentId));
    }

    /**
     * deleted set 에 삭제된 comment Id 제거
     * @param projectId
     * @param commentId
     */
    public void removeDeletedCommentId(Integer projectId, Integer commentId) {
        redisTemplate.opsForSet().remove(deletedCommentsKey(projectId), String.valueOf(commentId));
    }

    /**
     * 특정 project의 deleted set 전체 삭제
     * @param projectId
     */
    public void clearDeletedCommentIds(Integer projectId) {
        redisTemplate.delete(deletedCommentsKey(projectId));
    }

    /**
     * Redis hash와 deleted set에서 comment 1개 삭제
     * @param projectId
     * @param commentId
     */
    public void deleteCommentState(Integer projectId, Integer commentId) {
        redisTemplate.opsForHash().delete(commentsKey(projectId), String.valueOf(commentId));
        removeDeletedCommentId(projectId, commentId);
    }

    /**
     * 특정 project의 comment를 Redis(comments hash, deleted_comments set)에서 전체 제거
     * @param projectId
     */
    public void clearProjectCommentStates(Integer projectId) {
        redisTemplate.delete(commentsKey(projectId));
        redisTemplate.delete(deletedCommentsKey(projectId));
    }

    /**
     * 특정 project의 코멘트 working set 존재 여부 확인
     * @param projectId
     * @return
     */
    public boolean hasWorkingSet(Integer projectId) {
        return redisTemplate.hasKey(commentsKey(projectId)) || redisTemplate.hasKey(deletedCommentsKey(projectId));
    }

    /**
     * MySQL에서 comment를 1개 조회한 뒤 state로 변환
     * @param projectId
     * @param commentId
     * @return
     */
    private CommentState loadSingleFromMysql(Integer projectId, Integer commentId) {
        Comment comment = commentRepository.findByIdAndProjectId(commentId, projectId)
                .orElseThrow(() -> new BusinessException(ErrorCode.COMMENT_NOT_FOUND));

        Map<Integer, List<Integer>> mentionUserIdsByCommentId = loadMentionUserIdsByCommentIds(List.of(comment.getId()));

        CommentState commentState = CommentState.from(
                comment,
                projectId,
                mentionUserIdsByCommentId.getOrDefault(comment.getId(), List.of())
        );

        save(commentState);

        return commentState;
    }

    /**
     * comment Id 목록을 기준으로 멘션된 User Id Map 생성
     * @param commentIds
     * @return
     */
    private Map<Integer, List<Integer>> loadMentionUserIdsByCommentIds(List<Integer> commentIds) {
        if (commentIds.isEmpty()) {
            return Map.of();
        }

        List<CommentMention> mentions = commentMentionRepository.findAllByCommentIds(commentIds);

        return mentions.stream()
                .collect(Collectors.groupingBy(
                                mention -> mention.getComment().getId(),
                                Collectors.mapping(mention -> mention.getUser().getId(), Collectors.toList())
                        )
                );
    }

    /**
     * 특정 부모 comment의 자식인지 판별
     * @param commentStateList
     * @param target
     * @param ancestorCommentId
     * @return
     */
    private boolean isDescendantOf(
            List<CommentState> commentStateList,
            CommentState target,
            Integer ancestorCommentId
    ) {
        Map<Integer, CommentState> stateMap = commentStateList.stream()
                .collect(Collectors.toMap(CommentState::getCommentId, Function.identity(), (a, b) -> a));

        Integer currentParentId = target.getParentCommentId();

        while (currentParentId != null) {
            if (ancestorCommentId.equals(currentParentId)) {
                return true;
            }

            CommentState parent = stateMap.get(currentParentId);
            if (parent == null) {
                return false;
            }

            currentParentId = parent.getParentCommentId();
        }

        return false;
    }

    /**
     * Redis 시퀀스가 없는 경우, MySQL max id 기준으로 초기화
     */
    private void initializeCommentIdSequenceIfNeeded() {
        Boolean exists = redisTemplate.hasKey(COMMENT_ID_SEQ_KEY);
        if (Boolean.TRUE.equals(exists)) {
            return;
        }

        Integer maxId = commentRepository.findMaxId();
        redisTemplate.opsForValue().set(COMMENT_ID_SEQ_KEY, String.valueOf(maxId == null ? 0 : maxId));
    }

    /**
     * Redis JSON 문자열을 CommentState로 역직렬화
     * @param json
     * @return
     */
    private CommentState readCommentState(String json) {
        try {
            return objectMapper.readValue(json, CommentState.class);
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR, "Redis에 저장된 코멘트를 역직렬화하던 중 에러 발생");
        }
    }

    /**
     * comment 정렬 기준 생성
     * @return
     */
    private Comparator<CommentState> defaultOrder() {
        return Comparator
                .comparing(CommentState::getTrackId, Comparator.nullsLast(Integer::compareTo))
                .thenComparing(CommentState::getLocation, Comparator.nullsLast(java.math.BigDecimal::compareTo))
                .thenComparing(CommentState::getCreatedAt, Comparator.nullsLast(Instant::compareTo))
                .thenComparing(CommentState::getCommentId, Comparator.nullsLast(Integer::compareTo));
    }

    /**
     * Redis hash Key 생성 (Project Comment Hash Key)
     * @param projectId
     * @return
     */
    private String commentsKey(Integer projectId) {
        return COMMENTS_KEY.formatted(projectId);
    }

    /**
     * Redis set Key 생성 (Project Comment Deleted Set Key)
     * @param projectId
     * @return
     */
    private String deletedCommentsKey(Integer projectId) {
        return DELETED_COMMENTS_KEY.formatted(projectId);
    }

    private List<CommentState> loadAllFromMysql(Integer projectId) {
        List<Comment> comments = commentRepository.findAllByProjectId(projectId);
        if (comments.isEmpty()) {
            return List.of();
        }

        Map<Integer, List<Integer>> mentionUserIdsByCommentId = loadMentionUserIdsByCommentIds(
                comments.stream().map(Comment::getId).toList()
        );

        return comments.stream()
                .map(comment -> CommentState.from(
                        comment,
                        projectId,
                        mentionUserIdsByCommentId.getOrDefault(comment.getId(), List.of())
                ))
                .toList();
    }
}
