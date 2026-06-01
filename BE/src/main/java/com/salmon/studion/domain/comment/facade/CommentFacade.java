package com.salmon.studion.domain.comment.facade;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.service.UserService;
import com.salmon.studion.domain.comment.dto.redis.CommentState;
import com.salmon.studion.domain.comment.dto.response.CommentsGetResponse;
import com.salmon.studion.domain.comment.dto.websocket.*;
import com.salmon.studion.domain.comment.service.CommentService;
import com.salmon.studion.domain.project.service.ProjectMemberService;
import com.salmon.studion.domain.track.service.TrackService;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

@Component
@RequiredArgsConstructor
public class CommentFacade {

    private final CommentService commentService;
    private final ProjectMemberService projectMemberService;
    private final TrackService trackService;
    private final UserService userService;

    @Transactional
    public CommentCreateResponse createComment(CommentCreateRequest request, Integer userId) {
        request.validate();
        projectMemberService.validateProjectMember(request.getProjectId(), userId);

        trackService.validateTrackInProjectWorkingSet(request.getProjectId(), request.getTrackId());

        validateParentComment(request.getParentCommentId(), request.getProjectId(), request.getTrackId());

        User user = userService.getUserByUserId(userId);

        List<Integer> mentionedUserIds = normalizeMentionIds(request.getMentionedUserIds());
        List<User> mentionedUsers = validateAndLoadMentionUsers(request.getProjectId(), mentionedUserIds);

        CommentState commentState = commentService.createComment(
                request.getProjectId(),
                request.getTrackId(),
                user,
                request.getParentCommentId(),
                request.getContent(),
                request.getLocation(),
                mentionedUserIds
        );
        
        return CommentCreateResponse.of(request.getProjectId(), commentState, user, mentionedUsers);
    }

    @Transactional(readOnly = true)
    public CommentsGetResponse getComments(Integer projectId, Boolean isResolved, Integer trackId, boolean mentionedMe, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        if (trackId != null) {
            trackService.validateTrackInProjectWorkingSet(projectId, trackId);
        }

        List<CommentState> commentStates = commentService.getComments(projectId, trackId, isResolved, mentionedMe, userId);

        if (commentStates.isEmpty()) {
            return CommentsGetResponse.from(List.of());
        }

        Map<Integer, User> usersById = loadUsersById(commentStates);

        return CommentsGetResponse.from(buildCommentDtoList(commentStates, usersById));
    }

    @Transactional(readOnly = true)
    public List<CommentsGetResponse.CommentDto> getCommentsForProjectDetail(Integer projectId, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);

        List<CommentState> commentStates = commentService.getComments(projectId, null, null, false, userId);
        if (commentStates.isEmpty()) {
            return List.of();
        }

        Map<Integer, User> usersById = loadUsersById(commentStates);
        return buildCommentDtoList(commentStates, usersById);
    }

    @Transactional(readOnly = true)
    public boolean hasCommentWorkingSet(Integer projectId) {
        return commentService.hasCommentWorkingSet(projectId);
    }

    @Transactional
    public CommentDeleteResponse deleteComment(CommentDeleteRequest request, Integer userId) {
        request.validate();
        projectMemberService.validateProjectMember(request.getProjectId(), userId);

        CommentState commentState = commentService.getCommentByProjectId(request.getCommentId(), request.getProjectId());
        validateCommentOwner(commentState, userId);

        commentService.deleteComment(request.getProjectId(), request.getCommentId());

        return CommentDeleteResponse.of(request.getProjectId(), commentState);
    }

    @Transactional
    public CommentStatusChangeResponse changeStatus(CommentStatusChangeRequest request, Integer userId) {
        request.validate();
        projectMemberService.validateProjectMember(request.getProjectId(), userId);

        CommentState commentState = commentService.getCommentByProjectId(request.getCommentId(), request.getProjectId());
        CommentState updatedState = commentService.changeResolved(commentState);

        return CommentStatusChangeResponse.of(request.getProjectId(), updatedState);
    }

    private void validateParentComment(Integer parentCommentId, Integer projectId, Integer trackId) {
        if (parentCommentId == null) {
            return;
        }

        CommentState parentComment = commentService.getCommentByProjectId(parentCommentId, projectId);
        if (!parentComment.getTrackId().equals(trackId)) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }
    }

    private void validateCommentOwner(CommentState commentState, Integer userId) {
        if (!commentState.getUserId().equals(userId)) {
            throw new BusinessException(ErrorCode.COMMENT_ACCESS_DENIED);
        }
    }

    private List<Integer> normalizeMentionIds(List<Integer> mentionedUserIds) {
        if (mentionedUserIds == null || mentionedUserIds.isEmpty()) {
            return List.of();
        }

        Set<Integer> uniqueIds = new LinkedHashSet<>(mentionedUserIds);
        uniqueIds.remove(null);
        return uniqueIds.stream().toList();
    }

    private List<User> validateAndLoadMentionUsers(Integer projectId, List<Integer> mentionedUserIds) {
        if (mentionedUserIds.isEmpty()) {
            return List.of();
        }

        List<Integer> memberUserIds = projectMemberService.getProjectMemberUserIds(projectId, mentionedUserIds);
        if (memberUserIds.size() != mentionedUserIds.size()) {
            throw new BusinessException(ErrorCode.COMMENT_ACCESS_DENIED, "프로젝트 멤버만 멘션할 수 있습니다.");
        }

        List<User> users = userService.getUsersByIds(mentionedUserIds);
        if (users.size() != mentionedUserIds.size()) {
            throw new BusinessException(ErrorCode.USER_NOT_FOUND);
        }

        return users;
    }
    private Map<Integer, User> loadUsersById(List<CommentState> commentStates) {
        Set<Integer> userIds = new LinkedHashSet<>();

        for (CommentState commentState : commentStates) {
            userIds.add(commentState.getUserId());
            userIds.addAll(commentState.getMentionedUserIds());
        }

        List<User> users = userService.getUsersByIds(userIds.stream().toList());

        return users.stream()
                .collect(HashMap::new, (map, user) -> map.put(user.getId(), user), HashMap::putAll);
    }

    private List<CommentsGetResponse.CommentDto> buildCommentDtoList(List<CommentState> commentStates, Map<Integer, User> usersById) {
        Map<Integer, List<CommentsGetResponse.CommentDto>> repliesByParentId = new HashMap<>();

        for (CommentState c : commentStates) {
            if (c.getParentCommentId() != null) {
                repliesByParentId
                        .computeIfAbsent(c.getParentCommentId(), k -> new ArrayList<>())
                        .add(toDto(c, usersById, List.of()));
            }
        }

        return commentStates.stream()
                .filter(c -> c.getParentCommentId() == null)
                .map(c -> toDto(c, usersById, repliesByParentId.getOrDefault(c.getCommentId(), List.of())))
                .toList();
    }

    private CommentsGetResponse.CommentDto toDto(
            CommentState commentState,
            Map<Integer, User> usersById,
            List<CommentsGetResponse.CommentDto> replies
    ) {
        User user = usersById.get(commentState.getUserId());
        if (user == null) {
            throw new BusinessException(ErrorCode.USER_NOT_FOUND);
        }

        List<CommentsGetResponse.UserSummary> mentionedUsers = commentState.getMentionedUserIds().stream()
                .map(usersById::get)
                .filter(java.util.Objects::nonNull)
                .map(CommentsGetResponse.UserSummary::from)
                .toList();

        return CommentsGetResponse.CommentDto.from(commentState, user, mentionedUsers, replies);
    }

}
