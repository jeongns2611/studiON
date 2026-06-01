package com.salmon.studion.domain.project.repository;

import com.salmon.studion.domain.project.entity.ProjectMember;
import io.lettuce.core.dynamic.annotation.Param;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ProjectMemberRepository extends JpaRepository<ProjectMember, Integer> {
    @Query("""
        SELECT pm.project.id
        FROM ProjectMember pm
        WHERE pm.user.id = :userId
    """)
    List<Integer> findProjectIdsByUserId(@Param("userId") Integer userId);

    @Query("""
        SELECT pm
        FROM ProjectMember pm
        JOIN FETCH pm.user
        WHERE pm.project.id IN :projectIds
    """)
    List<ProjectMember> findAllWithUserByProjectIdIn(List<Integer> projectIds);

    boolean existsByProject_IdAndUser_Id(Integer projectId, Integer userId);

    @Query("""
        SELECT pm.user.id
        FROM ProjectMember pm
        WHERE pm.project.id = :projectId
          AND pm.user.id IN :userIds
    """)
    List<Integer> findUserIdsInProject(
            @Param("projectId") Integer projectId,
            @Param("userIds") List<Integer> userIds
    );

    // TODO: 유저테스트 전용 임시 구현 (추후 수정 필요 - countByProject_Id())
    long countByProject_Id(Integer projectId);

}
