package com.salmon.studion.domain.auth.repository;

import com.salmon.studion.domain.auth.entity.PositionGroup;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PositionGroupRepository extends JpaRepository<PositionGroup, Integer> {
    List<PositionGroup> findAllByOrderByOrderAsc();
}
