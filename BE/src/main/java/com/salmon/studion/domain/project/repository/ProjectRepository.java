package com.salmon.studion.domain.project.repository;

import com.salmon.studion.domain.project.entity.Project;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ProjectRepository extends JpaRepository<Project, Integer> {
    List<Project> findByIdInOrderByLastUpdateAtDesc(List<Integer> projectIds);
}
